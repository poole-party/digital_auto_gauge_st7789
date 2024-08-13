import busio
import board
import displayio
import math
import supervisor
import vectorio
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

# init the measurement vars
boost_raw = AnalogIn(board.A0)
# Need to figure out a different way to do this. Engine will be running and pulling vacuum before this can run.
boost_offset = getBoostOffset(boost_raw)
boost_pressure = boost_raw.value / 1000 - boost_offset
max_boost = 10
max_vacuum = -15
thermistor = AnalogIn(board.A2)
oil_temp = getTempFromADC(thermistor.value)
temp_samples_index = 0
sample_size = 50
oil_temp_samples = [oil_temp] * sample_size
start_boost_loop = 0
start_oil_loop = 0
last_loop = 101

# init the display and define the display context
display_height = 320
display_width = 240
screen = displayio.Group()
bar_group = displayio.Group()
gauge_group = displayio.Group()

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
bar_palette = displayio.Palette(3)
bar_palette[0] = 0x3040ff
bar_palette[1] = 0xff0303
bar_palette[2] = 0xdddddd


# === build boost gauge ===
boost_readout_y_pos = display_height / 2 - 6

boost_label = label.Label(sairaSmall, text="BOOST", color=label_color)
boost_label.anchor_point = (0.0, 0.0)
boost_label.anchored_position = (labels_x_pos, 5)

# boost_units = label.Label(sairaSmall, text="psi", color=0xffffff)
# boost_units.anchor_point = (1.0, 1.0)
# boost_units.anchored_position = (units_x_pos, boost_readout_y_pos)

# create a list of polygons that we can toggle visibility of to simulate a filled arc for the boost and vacuum bars
segments = 10
radius = 135
arc_width = 30
origin = {
	'x': display_width - 100,
	'y': boost_readout_y_pos - 6
}

# points = []
# start_angle = 45
# spread_angle = 135
# radius = radius + 2
# arc_width = arc_width + 4
# for i in range(segments * 2):
# 	alpha = (i * spread_angle / (segments * 2) + start_angle) / 180 * math.pi
# 	x = int(radius * math.cos(alpha))
# 	y = -int(radius * math.sin(alpha))
# 	points.append((x,y))

# for i in range(segments * 2, -1, -1):
# 	alpha = (i * spread_angle / (segments * 2) + start_angle) / 180 * math.pi
# 	x = int((radius - arc_width) * math.cos(alpha))
# 	y = -int((radius - arc_width) * math.sin(alpha))
# 	points.append((x,y))

# template_bar = vectorio.Polygon(
# 	pixel_shader=bar_palette,
# 	points=points,
# 	x=int(origin['x']),
# 	y=int(origin['y'])
# )
template_bar = Arc(
	x=int(origin['x']),
	y=int(origin['y']),
	radius=radius + 2,
	angle=135,
	direction=45 + 67.5,
	segments=segments * 2,
	arc_width=arc_width + 4,
	fill=None,
	outline=bar_palette[2]
)
bar_group.append(template_bar)

boost_bar = [None] * segments
start_angle = 45
spread_angle = 90
for i in range(segments):
	reverse_index = segments - i - 1
	points = [None] * 4
	for j in range(2):
		alpha = ((i+j) * spread_angle / segments + start_angle) / 180 * math.pi
		x0 = int(radius * math.cos(alpha))
		y0 = -int(radius * math.sin(alpha))
		x1 = int((radius - arc_width) * math.cos(alpha))
		y1 = -int((radius - arc_width) * math.sin(alpha))
		points[0 + j] = (x0,y0)
		points[3 - j] = (x1,y1)

	boost_bar[reverse_index] = vectorio.Polygon(
		pixel_shader=bar_palette,
		points=points,
		x=int(origin['x']),
		y=int(origin['y'])
	)

	# reverse the order of the segments so it's more intuitive to make the bar appear to fill or empty
	bar_group.append(boost_bar[reverse_index])
	boost_bar[reverse_index].hidden = True

vacuum_bar = [None] * segments
start_angle = 135
spread_angle = 45
for i in range(segments):
	points = [None] * 4
	for j in range(2):
		alpha = ((i+j) * spread_angle / segments + start_angle) / 180 * math.pi
		x0 = int(radius * math.cos(alpha))
		y0 = -int(radius * math.sin(alpha))
		x1 = int((radius - arc_width) * math.cos(alpha))
		y1 = -int((radius - arc_width) * math.sin(alpha))
		points[0 + j] = (x0,y0)
		points[3 - j] = (x1,y1)

	vacuum_bar[i] = vectorio.Polygon(
		pixel_shader=bar_palette,
		points=points,
		x=int(origin['x']),
		y=int(origin['y'])
	)

	bar_group.append(vacuum_bar[i])
	vacuum_bar[i].color_index = 1
	vacuum_bar[i].hidden = True


boost_readout_major = label.Label(
	saira,
	text=str(f'{boost_pressure:.1f}').split('.')[0],
	color=0xffffff
)
boost_readout_major.anchor_point = (1.0, 1.0)
boost_readout_major.anchored_position = (display_width - 60, boost_readout_y_pos - 3)

boost_readout_minor = label.Label(
	saira_mid,
	text='.' + str(f'{boost_pressure:0.1f}').split('.')[-1],
	color=0xffffff
)
boost_readout_minor.anchor_point = (0.0, 1.0)
boost_readout_minor.anchored_position = (display_width - 64, boost_readout_y_pos - 3)

# bar_group.append(template_bar)
gauge_group.append(boost_label)
# gauge_group.append(boost_units)
gauge_group.append(boost_readout_major)
gauge_group.append(boost_readout_minor)


# === build oil temp gauge ===
oil_temp_label = label.Label(sairaSmall, text="OIL TEMP", color=label_color)
oil_temp_label.anchor_point = (0.0, 0.0)
oil_temp_label.anchored_position = (labels_x_pos, display_height / 2 + 5)

# since the startup temp is unknown, hide these units and the associated readout
# on initial render by setting their color to 0x000000
# the actual display color will be determined in the first iteration of the update loop below
oil_temp_units = label.Label(sairaSmall, text="°F", color=0x000000)
oil_temp_units.anchor_point = (1.0, 1.0)
oil_temp_units.anchored_position = (units_x_pos, display_height - 10)

oil_temp_readout = label.Label(
	saira,
	text=str(int(oil_temp)),
	color=0x000000
)
oil_temp_readout.anchor_point = (1.0, 1.0)
oil_temp_readout.anchored_position = (display_width - 34, display_height - 10)

gauge_group.append(oil_temp_label)
gauge_group.append(oil_temp_units)
gauge_group.append(oil_temp_readout)


# render gauges on display
screen.append(bar_group)
screen.append(gauge_group)

# --- testing ---
# counting_up = True

# update loop
while True:
	# update boost readout value every 100ms
	if (last_loop - start_boost_loop > 10):
		# --- testing ---
		# if (counting_up):
		# 	boost_pressure += .6
		# 	if (boost_pressure >= max_boost): counting_up = False
		# else:
		# 	boost_pressure -= .6
		# 	if (boost_pressure <= max_boost * -1): counting_up = True
		# -- end testing --
		boost_pressure = boost_raw.value / 1000 - boost_offset
		boost_pressure_string_list = str(f'{boost_pressure:.1f}').split('.')
		boost_readout_major.text = boost_pressure_string_list[0]
		boost_readout_minor.text = '.' + boost_pressure_string_list[-1]
		boost_segments_to_show = math.fabs(math.ceil((int(boost_pressure * 10) / int(max_boost * 10)) * segments))
		if (boost_segments_to_show > segments):
			boost_segments_to_show = segments

		for i in range(segments):
			boost_bar[i].hidden = True
			vacuum_bar[i].hidden = True

		if (boost_pressure > 0):
			for i in range(boost_segments_to_show):
				if (i < boost_segments_to_show):
					boost_bar[i].hidden = False
				else:
					boost_bar[i].hidden = True
		elif (boost_pressure < 0):
			for i in range(boost_segments_to_show):
				if (i < boost_segments_to_show):
					vacuum_bar[i].hidden = False
				else:
					vacuum_bar[i].hidden = True

		start_boost_loop = supervisor.ticks_ms()

	# calculating temp from the raw thermistor value is expensive, so only update every second
	if (last_loop - start_oil_loop > 1000):
		oil_temp = getTempFromADC(thermistor.value)
		oil_temp_damped = '- - '
		oil_temp_samples[temp_samples_index] = int(oil_temp)
		temp_samples_index = (temp_samples_index + 1) % sample_size

		if (oil_temp < 0):
			update_color = 0xffffff
		else:
			oil_temp_damped = sum(oil_temp_samples) / len(oil_temp_samples)
			oil_temp_damped = str(int(oil_temp_damped))
			if (oil_temp < 200):
				# blue
				update_color = 0x3040ff
			elif (oil_temp < 270):
				# white
				update_color = 0xffffff
			else:
				# red
				update_color = 0xff2020

		oil_temp_units.color = update_color
		oil_temp_readout.color = update_color
		oil_temp_readout.text = oil_temp_damped
		start_oil_loop = supervisor.ticks_ms()

	last_loop = supervisor.ticks_ms()

	# if supervisor.ticks rolls over, reset all of the counters so the gauge doesn't freeze
	if (start_boost_loop > last_loop or start_oil_loop > last_loop):
		start_boost_loop = 0
		start_oil_loop = 0
		last_loop = 101
