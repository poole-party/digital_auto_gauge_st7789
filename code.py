import board
import busio
import displayio
import math
import rotaryio
import time
from adafruit_bitmap_font import  bitmap_font
from adafruit_display_shapes.arc import Arc
from adafruit_display_text import label
from adafruit_st7789 import ST7789
from analogio import AnalogIn
from fourwire import FourWire
from gauge import Gauge

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

# init the oil temperature measurement vars
thermistor = AnalogIn(board.A2)

# init the display and define the display context
display_height = 320
display_width = 240
screen = displayio.Group()

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
# sairaSmall = bitmap_font.load_font("fonts/saira-semibold-20pt.bdf")
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

active_gauges = []

#	=====================================================================
#	[							boost gauge								]
#	=====================================================================


active_gauges.append(Gauge(
	gauge_type = 'boost',
	origin = { 'x': display_width - 100, 'y': display_height / 2 - 12 },
	radius = 135,
	arc_width = 30,
	angles = {'start': 45, 'spread': 90, 'secondary_spread': 45},
	primary_segments = 20,
	primary_color_index = 1,
	palette = bar_palette,
	readout_pos = { 'x': display_width - 60, 'y': display_height / 2 - 9, 'x-minor': display_width - 64 },
	secondary = True,
	secondary_segments = 10,
	secondary_color_index = 15,
))


#	=====================================================================
#	[							oil temp gauge							]
#	=====================================================================


active_gauges.append(Gauge(
	gauge_type = 'temperature',
	origin = { 'x': display_width - 100, 'y': display_height - 10 },
	radius = 135,
	arc_width = 30,
	angles = {'start': 45, 'spread': 135},
	primary_segments = 20,
	primary_color_index = 1,
	palette = bar_palette,
	readout_pos = { 'x': display_width - 6, 'y': display_height - 10 },
))

# render gauges on display
for gauge in active_gauges:
	screen.append(gauge.group)


#	=====================================================================
#	[							update loop								]
#	=====================================================================
while True:
	# # check the encoder state and adjust data accordingly
	# current_position = encoder.position
	# if (current_position > last_position):
	# 	test_temp += 1
	# elif (current_position < last_position):
	# 	test_temp -= 1

	# last_position = current_position

	options = {}
	options['demo'] = True

	active_gauges[0].update_gauge(
		value = 'boost_raw.value',
		options = options
	)

	# TODO: add units to options array and create defaults in gauge.py
	active_gauges[1].update_gauge(
		value = 'thermistor.value',
		options = options
	)

	# time.sleep(0.2)
	# last_loop = supervisor.ticks_ms()

	# # if supervisor.ticks rolls over, reset all of the counters so the gauge doesn't freeze
	# if (start_boost_loop > last_loop or start_oil_loop > last_loop):
	# 	start_boost_loop = 0
	# 	start_oil_loop = 0
	# 	last_loop = 101
