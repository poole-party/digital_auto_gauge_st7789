import busio
import board
import displayio
import math
import supervisor
import vectorio
from adafruit_bitmap_font import  bitmap_font
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
max_boost = 25
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
sairaSmall = bitmap_font.load_font("fonts/saira-semibold-20pt.bdf")
label_color = 0xff0303
labels_x_pos = 1
units_x_pos = display_width - 7
bar_height = 70
bar_palette = displayio.Palette(2)
bar_palette[0] = 0x0000aa
bar_palette[1] = 0xff0303


# === build boost gauge ===
boost_readout_y_pos = display_height / 2 - 6

boost_label = label.Label(sairaSmall, text="BOOST", color=label_color)
boost_label.anchor_point = (0.0, 0.0)
boost_label.anchored_position = (labels_x_pos, 5)

boost_units = label.Label(sairaSmall, text="psi", color=0xffffff)
boost_units.anchor_point = (1.0, 1.0)
boost_units.anchored_position = (units_x_pos, boost_readout_y_pos)

boost_bar = vectorio.Rectangle(
    pixel_shader = bar_palette,
    x = 0,
    y = int(boost_readout_y_pos - 31 - bar_height / 2),
    width = 1,
    height = bar_height,
    color_index = 0,
)
vacuum_bar = vectorio.Rectangle(
    pixel_shader = bar_palette,
    x = display_width - 1,
    y = int(boost_readout_y_pos - 31 - bar_height / 2),
    width = 1,
    height = bar_height,
    color_index = 1
)

boost_readout = label.Label(
    saira,
    text=str(f'{boost_pressure:5.1f}'),
    color=0xffffff
)
boost_readout.anchor_point = (1.0, 1.0)
boost_readout.anchored_position = (display_width - 42, boost_readout_y_pos - 3)

bar_group.append(boost_bar)
bar_group.append(vacuum_bar)
boost_bar.hidden = True
vacuum_bar.hidden = True
gauge_group.append(boost_label)
gauge_group.append(boost_units)
gauge_group.append(boost_readout)


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
counting_up = True

# update loop
while True:
    # update boost readout value every 100ms
    if (last_loop - start_boost_loop > 50):
        # --- testing ---
        if (counting_up):
            boost_pressure += .5
            if (boost_pressure >= max_boost): counting_up = False
        else:
            boost_pressure -= .5
            if (boost_pressure <= max_boost * -1): counting_up = True
        # -- end testing --
        # boost_pressure = boost_raw.value / 1000 - boost_offset
        boost_readout.text = str(f'{boost_pressure:5.1f}')

        if (boost_pressure > 0):
            vacuum_bar.hidden = True
            if (boost_pressure > max_boost): max_boost = boost_pressure
            boost_bar.width = int(boost_pressure / max_boost * display_width)
            boost_bar.hidden = False
        elif (boost_pressure < 0):
            boost_bar.hidden = True
            if (boost_pressure < max_vacuum): max_vacuum = boost_pressure
            vacuum_bar_width = int(boost_pressure / max_vacuum * display_width)
            vacuum_bar.width = vacuum_bar_width
            vacuum_bar.x = display_width - vacuum_bar_width
            vacuum_bar.hidden = False
        else:
            boost_bar.hidden = True
            vacuum_bar.hidden = True

        start_boost_loop = supervisor.ticks_ms()

    # update temp readout value every 200ms
    if (last_loop - start_oil_loop > 200):
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
