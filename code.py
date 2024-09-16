import board
import busio
import displayio
import math
import rotaryio
import supervisor
import vectorio
from gauge import Gauge
from adafruit_bitmap_font import  bitmap_font
from adafruit_display_shapes.arc import Arc
from adafruit_display_text import label
from adafruit_st7789 import ST7789
from analogio import AnalogIn
from fourwire import FourWire

def getTempFromADC(thermistor):
	if (thermistor == 0): return 0
	R0 = 10000
	rT = R0 * (65535 / thermistor - 1)
	logRT = math.log(rT)

	# steinhart constants
	A = 0.0009086268490
	B = 0.0002045041393
	C = 0.0000001912131738

	kelvin = 1 / (A + (B * logRT) + C * math.pow(logRT, 3))
	celsius = kelvin - 273.15
	fahrenheit = celsius * 9 / 5 + 32

	print('\ntherm raw value: ', thermistor)
	print('adjusted raw: ', 65535 / thermistor - 1)
	print(celsius)

	return fahrenheit

def getBoostOffset(boost_raw):
	offset_samples = [0] * 100
	for i in range(100):
		offset_samples[i] = boost_raw.value / 1000

	boost_offset = sum(offset_samples) / len(offset_samples)
	return boost_offset

# Release any resources currently in use for the displays
displayio.release_displays()

# init the spi bus and allocate the requisite pins
spi = busio.SPI(clock=board.GP10, MOSI=board.GP11)
tft_cs = board.GP13
tft_dc = board.GP12
tft_reset = board.GP9

# init the rotary encoder and allocate pins
encoder = rotaryio.IncrementalEncoder(board.GP0, board.GP1)
last_position = 0

# init the manifold pressure measurement vars
boost_raw = AnalogIn(board.A0)
# Need to figure out a different way to do this. Engine will be running and pulling vacuum before this can run.
boost_offset = getBoostOffset(boost_raw)
boost_pressure = boost_raw.value / 1000 - boost_offset
max_boost = 10
max_vacuum = 15
# manifold differential pressure (MDP): the difference between the pressure in the intake manifold and the ambient air pressure
mdp_current = 0
mdp_next = boost_raw.value / 1000 - boost_offset
bar_level_current = 0
bar_level_next = 0
start_boost_loop = 0

print('\nboost offset: ', boost_offset)
print('boost value: ', boost_raw.value)

# init the oil temperature measurement vars
thermistor = AnalogIn(board.A2)
oil_temp = getTempFromADC(thermistor.value)
max_oil_temp = 300
temp_samples_index = 0
sample_size = 50
oil_temp_samples = [oil_temp] * sample_size
oil_temp_level_next = 0
oil_temp_level_current = -1
start_oil_loop = 0

last_loop = 101

# init the display and define the display context
display_height = 320
display_width = 240
screen = displayio.Group()
active_gauges = displayio.Group()

while not spi.try_lock():
	pass

spi.configure(baudrate=24000000) # Configure SPI for 24MHz
spi.unlock()

display_bus = FourWire(
	spi,
	command = tft_dc,
	chip_select = tft_cs,
	reset = tft_reset
)

display = ST7789(
	display_bus,
	width = display_width,
	height = display_height,
)

display.root_group = screen

color_bitmap = displayio.Bitmap(display_width, display_height, 1)
# display.rotation = 180

# common vars shared by both gauges
saira = bitmap_font.load_font("fonts/saira-bold-italic-56pt.bdf")
saira_mid = bitmap_font.load_font("fonts/saira-bold-italic-43pt-60.bdf")
sairaSmall = bitmap_font.load_font("fonts/saira-semibold-20pt.bdf")
label_color = 0xff0303
labels_x_pos = 1
units_x_pos = display_width - 7
bar_height = 70
bar_palette = displayio.Palette(17)
bar_palette[0] = 0xdddddd
bar_palette[1] = 0x00aaff
bar_palette[2] = 0x00c8fa
bar_palette[3] = 0x00e4fa
bar_palette[4] = 0x00fae5
bar_palette[5] = 0x00ff80
bar_palette[6] = 0x03ff03
bar_palette[7] = 0x55ff00
bar_palette[8] = 0xb7ff00
bar_palette[9] = 0xe1ff00
bar_palette[10] = 0xffff00
bar_palette[11] = 0xfff700
bar_palette[12] = 0xffd500
bar_palette[13] = 0xff9500
bar_palette[14] = 0xff5500
bar_palette[15] = 0xff0303
bar_palette[16] = 0xffffff

gauges = []

#	=====================================================================
#	[							boost gauge								]
#	=====================================================================


gauges.append(Gauge(
	gauge_type = 'boost',
	origin = { 'x': display_width - 100, 'y': display_height / 2 - 12 },
	radius = 135,
	arc_width = 30,
	angles = {'start': 45, 'spread': 90, 'secondary_spread': 45},
	primary_segments = 20,
	primary_color_index = 1,
	palette = bar_palette,
	readout_major = str(f'{boost_pressure:.1f}').split('.')[0],
	readout_pos = { 'x': display_width - 60, 'y': display_height / 2 - 9, 'x-minor': display_width - 64 },
	secondary_segments = 10,
	secondary_color_index = 15,
	readout_minor = '.' + str(f'{boost_pressure:0.1f}').split('.')[-1]
))


#	=====================================================================
#	[							oil temp gauge							]
#	=====================================================================

oil_temp_segments = 20
radius = 135
arc_width = 30
origin = {
	'x': display_width - 100,
	'y': display_height - 10
}

oil_temp_template_bar = Arc(
	x=int(origin['x']),
	y=int(origin['y']),
	radius=radius + 2,
	angle=135,
	direction=45 + 67.5,
	segments=oil_temp_segments,
	arc_width=arc_width + 4,
	fill=None,
	outline=bar_palette[0]
)
active_gauges.append(oil_temp_template_bar)

oil_temp_bar = [None] * oil_temp_segments
start_angle = 45
spread_angle = 135
for i in range(oil_temp_segments):
	reverse_index = oil_temp_segments - i - 1
	points = [None] * 4
	for j in range(2):
		alpha = ((i+j) * spread_angle / oil_temp_segments + start_angle) / 180 * math.pi
		x0 = int(radius * math.cos(alpha))
		y0 = -int(radius * math.sin(alpha))
		x1 = int((radius - arc_width) * math.cos(alpha))
		y1 = -int((radius - arc_width) * math.sin(alpha))
		points[0 + j] = (x0,y0)
		points[3 - j] = (x1,y1)

	oil_temp_bar[reverse_index] = vectorio.Polygon(
		pixel_shader=bar_palette,
		points=points,
		x=int(origin['x']),
		y=int(origin['y'])
	)

	# reverse the order of the segments so it's more intuitive to make the bar appear to fill or empty
	active_gauges.append(oil_temp_bar[reverse_index])
	oil_temp_bar[reverse_index].hidden = True

# oil_temp_bar[0].hidden = False

oil_temp_bar[0].color_index = 2
oil_temp_bar[1].color_index = 3
oil_temp_bar[2].color_index = 4
oil_temp_bar[3].color_index = 5
oil_temp_bar[4].color_index = 6
oil_temp_bar[5].color_index = 6
oil_temp_bar[6].color_index = 6
oil_temp_bar[7].color_index = 6
oil_temp_bar[8].color_index = 7
oil_temp_bar[9].color_index = 8
oil_temp_bar[10].color_index = 9
oil_temp_bar[11].color_index = 10
oil_temp_bar[12].color_index = 10
oil_temp_bar[13].color_index = 10
oil_temp_bar[14].color_index = 11
oil_temp_bar[15].color_index = 12
oil_temp_bar[16].color_index = 13
oil_temp_bar[17].color_index = 14
oil_temp_bar[18].color_index = 15
oil_temp_bar[19].color_index = 15

oil_temp_readout = label.Label(
	saira,
	text=str(int(oil_temp)),
	color=0xffffff
)
oil_temp_readout.anchor_point = (1.0, 1.0)
oil_temp_readout.anchored_position = (display_width - 6, display_height - 10)

# active_gauges.append(oil_temp_label)
# active_gauges.append(oil_temp_units)
active_gauges.append(oil_temp_readout)


# render gauges on display
for gauge in gauges:
	screen.append(gauge.group)
screen.append(active_gauges)

# --- testing ---
test_boost = 0
test_temp = 0
print('\n')
# -- end testing --


#	=====================================================================
#	[							update loop								]
#	=====================================================================
while True:
	# check the encoder state and adjust data accordingly
	current_position = encoder.position
	if (current_position > last_position):
		test_temp += 1
	elif (current_position < last_position):
		test_temp -= 1

	last_position = current_position

	# update boost readout value every 10ms
	# if (last_loop - start_boost_loop > 10):
	# 	gauges[0].update_boost_gauge(boost_raw.value, True)
	# 	start_boost_loop = supervisor.ticks_ms()
	gauges[0].update_gauge(
		gauge_type = 'boost',
		value = 'boost_raw.value',
		demo = True
	)



	# calculating temp from the raw thermistor value is expensive, so only update twice a second
	if (last_loop - start_oil_loop > 1000):
		oil_temp = getTempFromADC(thermistor.value)
		oil_temp_damped = '- - '
		oil_temp_samples[temp_samples_index] = int(oil_temp)
		temp_samples_index = (temp_samples_index + 1) % sample_size

		if (oil_temp > 0):
			oil_temp_damped = sum(oil_temp_samples) / len(oil_temp_samples)
			oil_temp_damped = int(oil_temp_damped)

# --- testing ---
		test_temp = ((test_temp + 5) % 120)
		oil_temp_damped = test_temp + 180
		oil_temp_level_next = int(test_temp / ((max_oil_temp - 180) / (oil_temp_segments - 1)))
# -- end testing --
		# oil_temp_level_next = int((oil_temp_damped - 180) / ((max_oil_temp - 180) / (oil_temp_segments - 1)))
		oil_temp_readout.text = str(oil_temp_damped)
		if (oil_temp_damped - 180) < 0:
			# set the level to zero if temp is below 180 so we don't get an index out of range error
			for i in range(oil_temp_segments):
				oil_temp_bar[i].hidden = True
			oil_temp_level_next = -1
		elif oil_temp_level_next > oil_temp_segments - 1:
			# if the bar is maxed out, set the level to the last segment so we don't get an index out of range error
			oil_temp_level_next = oil_temp_segments - 1
		elif (oil_temp_level_next > oil_temp_level_current):
			for i in range(oil_temp_level_current + 1, oil_temp_level_next + 1):
				oil_temp_bar[i].hidden = False
		elif (oil_temp_level_next < oil_temp_level_current):
			for i in range(oil_temp_level_current, oil_temp_level_next, -1):
				oil_temp_bar[i].hidden = True

		oil_temp_level_current = oil_temp_level_next
		start_oil_loop = supervisor.ticks_ms()

	last_loop = supervisor.ticks_ms()

	# if supervisor.ticks rolls over, reset all of the counters so the gauge doesn't freeze
	if (start_boost_loop > last_loop or start_oil_loop > last_loop):
		start_boost_loop = 0
		start_oil_loop = 0
		last_loop = 101
