import displayio
import math
import vectorio
from adafruit_bitmap_font import bitmap_font
from adafruit_display_shapes.arc import Arc
from adafruit_display_text import label
from temperature import Temperature

BOOST_OFFSET = 13.88
MAX_BOOST = 10
MAX_VACUUM = 15
MAX_TEMP = 300
READOUT_FONT_MAJOR = bitmap_font.load_font("fonts/saira-bold-italic-56pt.bdf")
READOUT_FONT_MINOR = bitmap_font.load_font("fonts/saira-bold-italic-43pt-60.bdf")
SAMPLE_SIZE = 50

class Gauge:
	def __init__(self, gauge_type, origin, radius, arc_width, angles, primary_segments, primary_color_index, palette, readout_pos, secondary = False, secondary_segments = None, secondary_color_index = None):
		self.gauge_type = gauge_type
		self.group = displayio.Group()
		self.primary_segments = primary_segments
		template_segments = primary_segments
		if secondary_segments:
			self.secondary_segments = secondary_segments
			template_segments += secondary_segments

		# build and add the hollow bar template
		self.template_bar = Arc(
			x=int(origin['x']),
			y=int(origin['y']),
			radius=radius + 2,
			angle=135,
			direction=45 + 67.5,
			segments=template_segments,
			arc_width=arc_width + 4,
			fill=None,
			outline=palette[0]
		)
		self.group.append(self.template_bar)

		# build and add the fill bar
		self.gauge_bar = [None] * primary_segments
		for i in range(primary_segments):
			reverse_index = primary_segments - i - 1
			points = [None] * 4
			for j in range(2):
				alpha = ((i+j) * angles['spread'] / primary_segments + angles['start']) / 180 * math.pi
				x0 = int(radius * math.cos(alpha))
				y0 = -int(radius * math.sin(alpha))
				x1 = int((radius - arc_width) * math.cos(alpha))
				y1 = -int((radius - arc_width) * math.sin(alpha))
				points[0 + j] = (x0,y0)
				points[3 - j] = (x1,y1)

			self.gauge_bar[reverse_index] = vectorio.Polygon(
				pixel_shader=palette,
				points=points,
				x=int(origin['x']),
				y=int(origin['y'])
			)
			# reverse the order of the segments so it's more intuitive to make the bar appear to fill or empty
			self.gauge_bar[reverse_index].hidden = True
			self.gauge_bar[reverse_index].color_index = primary_color_index
			self.group.append(self.gauge_bar[reverse_index])

		# if there is a secondary fill bar, build it and add it to the gauge group
		if secondary:
			self.gauge_bar_secondary = [None] * secondary_segments
			for i in range(secondary_segments):
				reverse_index = primary_segments + secondary_segments - i - 1
				points = [None] * 4
				for j in range(2):
					alpha = ((i+j) * angles['secondary_spread'] / secondary_segments + (angles['start'] + angles['spread'])) / 180 * math.pi
					x0 = int(radius * math.cos(alpha))
					y0 = -int(radius * math.sin(alpha))
					x1 = int((radius - arc_width) * math.cos(alpha))
					y1 = -int((radius - arc_width) * math.sin(alpha))
					points[0 + j] = (x0,y0)
					points[3 - j] = (x1,y1)

				self.gauge_bar_secondary[i] = vectorio.Polygon(
					pixel_shader=palette,
					points=points,
					x=int(origin['x']),
					y=int(origin['y'])
				)
				self.gauge_bar_secondary[i].hidden = True
				self.gauge_bar_secondary[i].color_index = secondary_color_index
				self.group.append(self.gauge_bar_secondary[i])

		# build and add the numeric readout
		self.readout = label.Label(
			READOUT_FONT_MAJOR,
			text='0',
			color=palette[16]
		)
		self.readout.anchor_point = (1.0, 1.0)
		self.readout.anchored_position = (readout_pos['x'], readout_pos['y'])
		self.group.append(self.readout)

		if secondary:
			self.readout_minor = label.Label(
				READOUT_FONT_MINOR,
				text='.0',
				color=palette[16]
			)
			self.readout_minor.anchor_point = (0.0, 1.0)
			self.readout_minor.anchored_position = (readout_pos['x-minor'], readout_pos['y'])
			self.group.append(self.readout_minor)

	def update_gauge(self, value, options = {}):
		if self.gauge_type == 'boost':
			self.update_boost(value, options)
		elif self.gauge_type == 'temperature' or self.gauge_type == 'temp':
			self.update_temperature(value, options)

	def update_boost(self, value, options = {}):
		try:
			if options['demo']:
				try:
					mdp_next = (self.test_value - 150) / 10
				except AttributeError:
					self.test_value = 0
					mdp_next = (self.test_value - 150) / 10

				self.test_value = ((self.test_value + 2) % 251)
		except KeyError:
			mdp_next = value / 1000 - BOOST_OFFSET

		if not hasattr(self, 'mdp_current'):
			self.mdp_current = mdp_next

		if not hasattr(self, 'bar_level_current'):
			self.bar_level_current = 0

		mdp_split_string = str(f'{mdp_next:.1f}').split('.')
		self.readout.text = mdp_split_string[0]
		self.readout_minor.text = '.' + mdp_split_string[-1]

		# change in boost only
		if (self.mdp_current > 0 and mdp_next > 0):
			bar_level_next = int(mdp_next / (MAX_BOOST / (self.primary_segments - 1)))
			# if the bar is maxed out, set the level to the last segment so we don't get an index out of range error
			if (bar_level_next >= self.primary_segments):
				bar_level_next = self.primary_segments - 1

			if (bar_level_next > self.bar_level_current or (self.gauge_bar[0].hidden and mdp_next >= 0.1)):
				for i in range(self.bar_level_current, bar_level_next + 1):
					self.gauge_bar[i].hidden = False
			elif (bar_level_next < self.bar_level_current):
				for i in range(self.bar_level_current, bar_level_next, -1):
					self.gauge_bar[i].hidden = True

		# change in vacuum only
		elif (self.mdp_current < 0 and mdp_next < 0):
			bar_level_next = int(math.fabs(mdp_next) / (MAX_VACUUM / (self.secondary_segments - 1)))
			# if the bar is maxed out, set the level to the last segment so we don't get an index out of range error
			if (bar_level_next >= self.secondary_segments):
				bar_level_next = self.secondary_segments - 1

			if (bar_level_next > self.bar_level_current or (self.gauge_bar_secondary[0].hidden and mdp_next <= -0.1)):
				for i in range(self.bar_level_current, bar_level_next + 1):
					self.gauge_bar_secondary[i].hidden = False
			elif (bar_level_next < self.bar_level_current):
				for i in range(self.bar_level_current, bar_level_next, -1):
					self.gauge_bar_secondary[i].hidden = True

		# change from boost to vacuum
		elif (self.mdp_current >= 0 and mdp_next < 0):
			bar_level_next = int(math.fabs(mdp_next) / (MAX_VACUUM / (self.secondary_segments - 1)))
			# if the bar is maxed out, set the level to the last segment so we don't get an index out of range error
			if (bar_level_next >= self.secondary_segments):
				bar_level_next = self.secondary_segments - 1

			# empty the boost bar
			for i in range(self.bar_level_current, -1, -1):
				self.gauge_bar[i].hidden = True

			# fill the vacuum bar
			for i in range(0, bar_level_next + 1):
				self.gauge_bar_secondary[i].hidden = False

		# change from vacuum to boost
		elif (self.mdp_current < 0 and mdp_next >= 0):
			bar_level_next = int(mdp_next / (MAX_BOOST / (self.primary_segments - 1)))
			# if the bar is maxed out, set the level to the last segment so we don't get an index out of range error
			if (bar_level_next >= self.primary_segments):
				bar_level_next = self.primary_segments - 1

			# empty the vacuum bar
			for i in range(self.bar_level_current, -1, -1):
				self.gauge_bar_secondary[i].hidden = True

			# fill the boost bar
			for i in range(0, bar_level_next + 1):
				self.gauge_bar[i].hidden = False

		self.mdp_current = mdp_next
		try :
			self.bar_level_current = bar_level_next
		except NameError:
			pass

	def update_temperature(self, value, options):
		try:
			if options['demo']:
				try:
					self.test_value = (self.test_value + 2) % 150
				except AttributeError:
					self.test_value = 0

				temp = self.test_value + 145
		except KeyError:
			temp = Temperature.lookup(value, options['units'])

		# if not hasattr(self, 'samples_index'):
		# 	self.samples_index = 0
		# if not hasattr(self, 'samples'):
		# 	self.samples = [temp] * SAMPLE_SIZE

		display_temp = '- - '
		# self.samples[self.samples_index] = int(temp)
		# self.samples_index = (self.samples_index + 1) % SAMPLE_SIZE

		if (temp > 0):
			# display_temp = sum(self.samples) / len(self.samples)
			# display_temp = int(display_temp)
			display_temp = temp
			temp_level_next = int((display_temp - 150) / ((MAX_TEMP - 150) / (self.primary_segments - 1)))
			if not hasattr(self, 'temp_level_current'):
				self.temp_level_current = -1

		self.readout.text = str(display_temp)

		# set the level to zero if temp is below 150 so we don't get an index out of range error
		if not isinstance(display_temp, int) or display_temp - 150 < 0:
			for i in range(self.primary_segments):
				self.gauge_bar[i].hidden = True
			temp_level_next = -1
		# if the bar is maxed out, set the level to the last segment so we don't get an index out of range error
		elif temp_level_next > self.primary_segments - 1:
			temp_level_next = self.primary_segments - 1
		elif (temp_level_next >= self.temp_level_current):
			for i in range(self.temp_level_current + 1, temp_level_next + 1):
				self.gauge_bar[i].hidden = False
		elif (temp_level_next < self.temp_level_current):
			for i in range(self.temp_level_current, temp_level_next, -1):
				self.gauge_bar[i].hidden = True

		self.temp_level_current = temp_level_next

	def __str__(self):
		return f'{self.name} {self.value}'

	def __repr__(self):
		return f'{self.name} {self.value}'