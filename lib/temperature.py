import math

TEMP_LOOKUP = {
	'32': {
		'32050': (66, 150),
	},
	'33': {
		'33000': (67, 153),
		'33950': (69, 156),
	},
	'34': {
		'34850': (71, 159),
	},
	'35': {
		'35750': (72, 162),
	},
	'36': {
		'36650': (74, 165),
	},
	'37': {
		'37550': (76, 168),
	},
	'38': {
		'38400': (77, 171),
	},
	'39': {
		'39250': (79, 174),
	},
	'40': {
		'40100': (81, 177),
		'40950': (82, 180),
	},
	'41': {
		'41750': (84, 183),
	},
	'42': {
		'42550': (86, 186),
	},
	'43': {
		'43300': (87, 189),
	},
	'44': {
		'44050': (89, 192),
		'44800': (91, 195),
	},
	'45': {
		'45525': (92, 198),
	},
	'46': {
		'46225': (94, 201),
		'46900': (96, 204),
	},
	'47': {
		'47550': (97, 207),
	},
	'48': {
		'48200': (99, 210),
		'48825': (101, 213),
	},
	'49': {
		'49425': (102, 216),
	},
	'50': {
		'50000': (104, 219),
		'50575': (106, 222),
	},
	'51': {
		'51125': (107, 225),
		'51650': (109, 228),
	},
	'52': {
		'52175': (111, 231),
		'52650': (112, 234),
	},
	'53': {
		'53150': (114, 237),
		'53600': (116, 240),
	},
	'54': {
		'54050': (117, 243),
		'54475': (119, 246),
		'54875': (121, 249),
	},
	'55': {
		'55275': (122, 252),
		'55650': (124, 255),
	},
	'56': {
		'56025': (126, 258),
		'56375': (127, 261),
		'56725': (129, 264),
	},
	'57': {
		'57050': (131, 267),
		'57360': (132, 270),
		'57675': (134, 273),
		'57950': (136, 276),
	},
	'58': {
		'58230': (137, 279),
		'58500': (139, 282),
		'58760': (141, 285),
	},
	'59': {
		'59020': (142, 288),
		'59250': (144, 291),
		'59480': (146, 294),
		'59700': (147, 297),
		'59920': (149, 300),
	},
}

class Temperature:
	def fahrenheit(self, value):
		subset_key = int(str(value)[:2])
		if subset_key < 32:
			return 0

		subset = TEMP_LOOKUP[subset_key]
		last_key = None
		for key in subset:
			if key == value:
				return subset[key][1]
			else:
				last_key = key
				if key > value:
					if (key - value) < math.fabs(value - key):
						return subset[key][1]
					else:
						return subset[last_key][1]

		return subset[last_key][1]

	def celsius(self, value):
		subset_key = int(str(value)[:2])
		if subset_key < 32:
			return 0

		subset = TEMP_LOOKUP[subset_key]
		last_key = None
		for key in subset:
			if key == value:
				return subset[key][0]
			else:
				last_key = key
				if key > value:
					if (key - value) < math.fabs(value - key):
						return subset[key][0]
					else:
						return subset[last_key][0]

		return subset[last_key][0]
