#! /usr/bin/python

#
# Copyright (c) 2015-2017 LabKey Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import sys
import os
import os.path
import shutil
import re
import subprocess

cwd = "./"
verbose = False


# OS Helpers

def call(args):
	if verbose:
		print "$", " ".join(args)
	return subprocess.call(args)


def check_output(args):
	if verbose:
		print "$", " ".join(args)
	return subprocess.check_output(args, stderr=subprocess.STDOUT)



# CONFIGURATION

class Config:
	name=None
	checkout=None
	repo=None
	path=None
	url=None
	branch=None
	_source=None		# used for merging

	def debug_print(self):
		print "[%s]\n\trepo=%s\n\tpath=%s\n\turl=%s\n\tbranch=%s" % (self.name, self.repo, self.path, self.url, self.branch)


	def validate(self):
		if self.checkout:
			if self.checkout.startswith("svn"):
				self.repo = "svn"
			if self.checkout.startswith("git"):
				self.repo = "git"
			m = re.search("\\s'?(https?://\\S*)", self.checkout)
			if m:
				self.url = m.group(1).strip("'")
			m = re.search("\\s(-b|--branch)\\s*'?(\\S*)", self.checkout)
			if m:
				self.branch = m.group(2).strip("'")

		if self.repo is None and self.checkout is not None:
			if self.checkout.startswith("svn"):
				self.repo = "svn"
			if self.checkout.startswith("git"):
				self.repo = "git"

		if self.path is None:
			self.path = self.name


	def write(self, f):
		if self._source:
			f.write(self._source)
			return
		f.write("[" + self.path + "]\n")
		if self.checkout:
			f.write("checkout = ")
			f.write(self.checkout)
			f.write("\n")
			return
		if self.repo == "git":
			f.write("checkout = git clone ")
			f.write(self.url)
			if self.branch:
				f.write(" --branch ")
				f.write(self.branch)
			f.write("\n")
			return
		if self.repo == "svn":
			f.write("checkout = svn checkout ")
			f.write(self.url)
			f.write("\n")
			return
		print "!could not format configuration for " + self.path


def config_from_repos(rel_path):
	if os.path.isdir(rel_path + "/.git"):
		return config_from_git(rel_path)
	elif os.path.isdir(rel_path + "/.svn"):
		return config_from_svn(rel_path)
	return None


def config_from_svn(rel_path):
	os.chdir(cwd + "/" + rel_path)
	config = Config()
	config.path = rel_path
	config.repo = "svn"
	info = check_output(["svn", "info"])
	for line in info.split("\n"):
		if line.startswith("URL: "):
			config.url = line[5:].strip()
	os.chdir(cwd)
	return config


def config_from_git(rel_path):
	os.chdir(cwd + "/" + rel_path)
	config = Config()
	config.path = rel_path
	config.repo = "git"
	config.url = check_output(["git", "config", "--get", "remote.origin.url"]).strip()
	branches = check_output(["git", "branch"])
	branches = branches.split("\n")
	for branch in branches:
		if branch.startswith("*"):
			config.branch = branch[2:].strip()
	os.chdir(cwd)
	return config


# ENLIST

def enlist(config):
	os.chdir(cwd)
	if not os.path.isdir(config.path):
		os.makedirs(config.path)
	if config.repo == "git":
		enlist_git(config)
		switch_git(config)
	elif config.repo == "svn":
		enlist_svn(config)
		switch_svn(config)
	os.chdir(cwd)


def enlist_git(config):
	if os.path.isdir(config.path + "/.git"):
		check(config)
		return
	call(["git", "clone", config.url, config.path])
	if not None == config.branch:
		call(["git", "checkout", config.branch])


def enlist_svn(config):
	if os.path.isdir(config.path + "/.svn"):
		check(config)
		return
	call(["svn", "checkout", config.url, config.path])


def enlist_sanity_check(configs):
	root_config = None
	for config in configs:
		if config.path == "." or config.path == "./":
			root_config = config
	repos_root = find_repository_root()
	if not repos_root:
		return True
	if not compare_paths(cwd,repos_root):
		print "! this does not seem to be a repository root"
		sys.exit(1)
	curr_config = config_from_repos(".")
	if curr_config and root_config and curr_config.repo != root_config.repo:
		print "! found existing " + curr_config.repo + " enlistment. expected " + root_config.repo
		sys.exit(1)

	#TODO: check if parent is a repository, etc.
	return True


def find_repository_root():
	global cwd

	try:
		info = check_output(["svn", "info"])
		for line in info.split("\n"):
			if line.startswith("Working Copy Root Path: "):
				return line[len("Working Copy Root Path: "):].strip()
	except subprocess.CalledProcessError:
		pass

	try:
		info = check_output(["git", "rev-parse", "--show-toplevel"])
		return info.strip()
	except subprocess.CalledProcessError:
		pass

	return None


def compare_paths(a,b):
	a = os.path.normpath(a)
	b = os.path.normpath(b)
	return a.lower() == b.lower()

# CHECK

def check(config):
	os.chdir(cwd)
	if not os.path.isdir(config.path):
		print "! directory does not exist: " + config.path
		return False
	ok = True
	if config.repo == "git":
		ok = check_git(config)
	elif config.repo == "svn":
		ok = check_svn(config)
	os.chdir(cwd)
	return ok


def check_git(config):
	if not os.path.isdir(config.path + "/.git"):
		print "! directory does not appear to have a git enlistment: " + config.path
		return False
	existing = config_from_git(config.path)
	return check_config(config,existing)


def check_svn(config):
	if not os.path.isdir(config.path + "/.svn"):
		print "! directory does not appear to have a svn enlistment: " + config.path
		return False
	existing = config_from_svn(config.path)
	return check_config(config,existing)


def check_config(config,existing):
	if existing.repo != config.repo:
		print "! found existing " + existing.repo + " repository, expected " + config.repo
		return False
	if not compare_url(existing.url,config.url):
		print "! wrong remote url: %s" % (existing.url)
		return False

	if config.repo == "git" and not existing.branch:
		print "! couldn't find current branch for %s" % (config.path)
		return False

	if config.branch and existing.branch != config.branch:
		print "! expected to find branch '%s' found '%s'" % (config.branch, existing.branch)
		return False

	return True


def strip_url(a):
	if not a:
		return ""
	a = a.lower()
	if a.startswith("http://"):
		a = a[7:]
	elif a.startswith("https://"):
		a = a[8:]
	if a.startswith("www."):
		a = a[4:]
	if a.endswith(".git"):
		a = a[:len(a)-4]
	return a


def compare_url(a,b):
	return strip_url(a) == strip_url(b)


def find_all_repos():
	global cwd
	repos = []
	for root, dirs, files in os.walk(cwd):
		if '.git' in dirs:
			dirs.remove('.git')
		if '.svn' in dirs:
			dirs.remove('.svn')
		if os.path.isdir(root + "/.svn") or os.path.isdir(root + "/.git"):
			repos.append(root)
	return repos

# SWITCH

def switch_svn(config):
	call(["svn", "switch", config.url])
	return


def switch_git(config):
	if config.branch is None:
		print "no branch specified for " + config.name
		return
	os.chdir(config.path)
	call(["git", "checkout", config.branch])
	return


# ADD/MERGE CONFIGURATION

def merge_configs(existing, apply):
	dict = {}
	merged = []
	changed = 0
	for i in range(0,len(existing)):
		config = existing[i]
		merged.append(config)
		dict[config.path.lower()] = i
	for config in apply:
		if dict.has_key(config.path.lower()):
			i = dict[config.path.lower()]
			orig = merged[i]
			if compare_url(orig.url, config.url) and orig.branch==config.branch:
				continue
			merged[i] = config
			print "updating config for " + config.path
			changed += 1
		else:
			merged.append(config)
			print "adding config for " + config.path
			changed += 1
	return merged, changed


# MAIN

def parse_property(line):
	i = line.find("=")
	if -1==i:
		return (None,None)
	return line[:i].strip(), line[i+1:].strip()


def parse_configuration_file(config_file):
	configs = []
	config = None
	section = ""
	defaults = {}

	f = open(config_file,"r")
	for rawline in f.readlines():
		line = rawline.strip()
		if line.startswith("#") or line=="":
			continue
		if line.startswith("[") and line.endswith("]"):
			if config is not None:
				configs.append(config)
				config = None
			section = line[1:len(line)-1]
			if section != "DEFAULT":
				config = Config()
				config.name = section
				config.source = line + "\n"
				continue
		(key,value) = parse_property(line)
		if not config:
			if section == "DEFAULT":
				if key and value:
					defaults[key] = value
			continue
		config.source = config.source + rawline + "\n"
		if key=="checkout":
			config.checkout = value
		elif key=="repo":
			config.repo = value
		elif key=="url":
			config.url = value
		elif key=="branch":
			config.branch = value
	f.close()

	if config is not None:
		configs.append(config)

	if not defaults.has_key('description') or not defaults['description']:
		print "! description not found: " + config_file
	elif verbose:
		print defaults['description']
	for config in configs:
		config.validate()
	return configs, defaults


def write_configuration_file(config_file, configs, defaults):
	f = open(config_file, "w")
	if defaults:
		f.write("[DEFAULT]\n")
		for k, v in defaults.iteritems():
			if k and v:
				f.write(k)
				f.write(" = ")
				f.write(v)
				f.write("\n")
		f.write("\n")
	for config in configs:
		config.write(f)
		f.write("\n")
	f.close()


def main(argv):
	global cwd
	global verbose
	cwd = os.getcwd()

	config_file = None
	command = "check"
	for arg in argv[1:]:
		if arg=="enlist" or arg=="check" or arg=="addconfig":
			command = arg
		elif arg=="-v":
			verbose = True
		else:
			config_file = arg

	if config_file is None and command != "addconfig":
		if os.path.isfile(".mrconfig"):
			config_file = ".mrconfig"
			if verbose:
				"using configuration file .mrconfig"

	if config_file is None or command is None:
		print "Usage: python enlist_main.py [enlist|check|addconfig] [-v] [config_file]"
		print "Usage: enlistconfig [-v] [config_file]"
		print "Usage: checkconfig [-v] [config_file]"
		print "Usage: addconfig [-v] [config_file]"
		print ""
		print "After successful enlist, you can omit the config file to use the enlisted configuration."
		print "The config_file is required for addconfig command."
		sys.exit(1)


	configs, defaults = parse_configuration_file(config_file)
	enlist_sanity_check(configs)

	if "enlist"==command:
		if ".mrconfig" != config_file:
			shutil.copyfile(config_file,".mrconfig")
		for config in configs:
			if verbose:
				config.debug_print()
			enlist(config)
			if verbose:
				print

	if "check"==command:
		OK = True
		for config in configs:
			if verbose:
				config.debug_print()
			else:
				print "[" +  config.path + "]"
			ret = check(config)
			if ret:
				print "ok"
			OK = OK and ret
			if verbose:
				print
		if verbose:
			repos = find_all_repos()
			for config in configs:
				full = os.path.normpath(cwd + "/" + config.path)
				if full in repos:
					repos.remove(full)
			if len(repos) > 0:
				print "looks like some repositories might not be registered"
				print "\n".join(repos)
		if OK:
			print "looks good"

	if "addconfig"==command:
		if ".mrconfig"==config_file:
			print "! addconfig command requires a source config file"
			sys.exit(1)
		local_configs = []
		if os.path.isfile(".mrconfig"):
			local_configs, local_defaults = parse_configuration_file(".mrconfig")
			if len(local_defaults) > 0:
				defaults = local_defaults

		merged_configs, changes = merge_configs(local_configs, configs)
		if changes == 0:
			print "no new configurations were found in : " + config_file
		else:
			write_configuration_file(".mrconfig", merged_configs, defaults)
			print changes, "configuration(s) added, run 'enlistconfig' or 'mr update' to apply"


if __name__ == "__main__":
	main(sys.argv)
