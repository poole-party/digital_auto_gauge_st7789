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
READOUT_FONT_MAJOR = bitmap_font.load_font("fonts/saira-bold-italic-56pt.bdf")
READOUT_FONT_MINOR = bitmap_font.load_font("fonts/saira-bold-italic-43pt-60.bdf")

class Gauge:
	def __init__(self, gauge_type, origin, radius, arc_width, angles, primary_segments, primary_color_index, palette, readout_major, readout_pos, secondary_segments = None, secondary_color_index = None, readout_minor = None):
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
		if secondary_segments:
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
			text=readout_major,
			color=palette[16]
		)
		self.readout.anchor_point = (1.0, 1.0)
		self.readout.anchored_position = (readout_pos['x'], readout_pos['y'])
		self.group.append(self.readout)
		if readout_minor:
			self.readout_minor = label.Label(
				READOUT_FONT_MINOR,
				text=readout_minor,
				color=palette[16]
			)
			self.readout_minor.anchor_point = (0.0, 1.0)
			self.readout_minor.anchored_position = (readout_pos['x'], readout_pos['y'])
			self.group.append(self.readout_minor)

	def get_template_bar(self):
		return self.template_bar

	def get_gauge_bar(self):
		return self.gauge_bar

	def update_gauge(self, gauge_type, value, demo):
		if gauge_type == 'boost':
			self.update_boost(value, demo)
		elif gauge_type == 'temperature':
			self.update_temperature(value, demo)

	def update_boost(self, value, demo=False):
		if demo:
			try:
				mdp_next = (self.test_value - 150) / 10
			except AttributeError:
				self.test_value = 0
				mdp_next = (self.test_value - 150) / 10

			self.test_value = ((self.test_value + 2) % 251)
		else:
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

	def update_temperature(self, value, demo=False):
		pass
