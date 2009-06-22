_debug = False

try:
	import gettext
except ImportError:
	# Instally dummy identity function
	import __builtin__
	__builtin__._ = lambda x: x
else:
	package_name = "kupfer"
	localedir = "./locale"
	try:
		import version_subst
	except ImportError:
		pass
	else:
		package_name = version_subst.PACKAGE_NAME
		localedir = version_subst.LOCALEDIR
	gettext.install(package_name, localedir=localedir)

def get_options(default_opts=""):
	""" Usage:
	--help          show usage help
	--debug         enable debug info

	list of sources:
	  a             applications
	  b             firefox bookmarks
	  c             recent documents
	  e             epiphany bookmarks
	  m             common items
	  p             nautilus places
	  s             gnu screen sessions
	  w             windows
	"""
	from getopt import getopt, GetoptError
	from sys import argv

	opts = argv[1:]
	if "--debug" in opts:
		try:
			import debug
		except ImportError, e:
			print e
		global _debug
		_debug = True
		opts.remove("--debug") 

	try:
		opts, args = getopt(opts, "", ["help"])
	except GetoptError, info:
		print info
		print get_options.__doc__
		raise SystemExit

	options = {}
	
	for k, v in opts:
		if k == "--help":
			print get_options.__doc__
			raise SystemExit

	return options

def get_config():
	import ConfigParser
	import os, sys

	cf_file = "kupfer.cfg"
	sep = ";"
	parser = ConfigParser.SafeConfigParser()
	default_plugins = (
			"common",
			"screen",
			"windows",
			"applications",
			"documents",
		)
	default_plugins_catalog = (
			"epiphany",
			"firefox",
		)
	default_directories = ("~/", "~/Desktop", )
	defaults = {
		"Plugins": {
			"Direct" : default_plugins,
			"Catalog" : default_plugins_catalog,
		},
		"Directories" : {
			"Direct" : default_directories,
			"Catalog" : (),
		},
		"DeepDirectories" : {
			"Direct" : (),
			"Catalog" : (),
			"Depth" : 2,
		},
	}
	# Set up defaults
	def fill_parser(parser, defaults):
		for secname, section in defaults.iteritems():
			if not parser.has_section(secname):
				parser.add_section(secname)
			for key, default in section.iteritems():
				if isinstance(default, (tuple, list)):
					default = sep.join(default)
				elif isinstance(default, int):
					default = str(default)
				parser.set(secname, key, default)

	fill_parser(parser, defaults)
	try:
		fil = open(cf_file, "r")
		parser.readfp(fil)
		fil.close()
	except IOError:
		pass

	for secname, section in defaults.iteritems():
		for key, default in section.iteritems():
			value = parser.get(secname, key)
			if isinstance(default, (tuple, list)):
				if not value:
					retval = ()
				else:
					retval = [p.strip() for p in value.split(sep) if p]
			elif isinstance(default, int):
				retval = type(default)(value)
			else:
				retval = str(value)
			defaults[secname][key] = retval

	print "Plugins:", defaults["Plugins"]["Direct"], defaults["Plugins"]["Catalog"]
	print "Directories:", defaults["Directories"]["Direct"]
	fill_parser(parser, defaults)
	fil = open(cf_file, "w")
	parser.write(fil)
	fil.close()
	return defaults

def main():
	import sys
	from os import path

	from . import browser
	from . import objects, plugin
	from . import data

	options = get_options()

	s_sources = []
	S_sources = []

	def dir_source(opt):
		abs = path.abspath(path.expanduser(opt))
		return objects.DirectorySource(abs)

	def file_source(opt, depth=1):
		abs = path.abspath(path.expanduser(opt))
		return objects.FileSource((abs,), depth)

	source_config = get_config()

	def import_plugin(name):
		path = ".".join(["kupfer", "plugin", name])
		plugin = __import__(path, fromlist=(name,))
		print "Loading plugin %s" % plugin.__name__
		return plugin

	sources_attribute = "__kupfer_sources__"
	def load_plugin_sources(plugin_name):
		try:
			plugin = import_plugin(plugin_name)
		except ImportError, e:
			print "Skipping module %s: %s" % (plugin_name, e)
			return
		try:
			sources = getattr(plugin, sources_attribute)
		except AttributeError, e:
			print "Plugin %s: %s" % (plugin_name, e)
			return
		for source_name in sources:
			source = getattr(plugin, source_name)
			yield source()

	for item in source_config["Plugins"]["Catalog"]:
		s_sources.extend(load_plugin_sources(item))
	for item in source_config["Plugins"]["Direct"]:
		S_sources.extend(load_plugin_sources(item))

	dir_depth = source_config["DeepDirectories"]["Depth"]

	for item in source_config["Directories"]["Catalog"]:
		s_sources.append(dir_source(item))
	for item in source_config["DeepDirectories"]["Catalog"]:
		s_sources.append(file_source(item, dir_depth))
	for item in source_config["Directories"]["Direct"]:
		S_sources.append(dir_source(item))
	for item in source_config["DeepDirectories"]["Direct"]:
		S_sources.append(file_source(item, dir_depth))
	
	if not S_sources and not s_sources:
		print "No sources"
		raise SystemExit(1)

	if _debug:
		from . import pretty
		pretty.debug = _debug

	dc = data.DataController()
	dc.set_sources(S_sources, s_sources)
	w = browser.WindowController()
	w.main()

