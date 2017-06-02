# -*- coding:utf-8 -*-
'''
Created on 2017.05.27

@author: davidpower

For implant versioning to our xgen workflow.

'''

import os
import json
from contextlib import contextmanager
import shutil
import distutils.dir_util as dir_util
import pymel.core as pm
import xgenm as xg
import xgenm.xgGlobal as xgg
import xgenm.XgExternalAPI as base

import mXGen; reload(mXGen)
import mXGen.msxgmExternalAPI as msxg; reload(msxg)


def linkedCheck(func):
	def deco(*args, **kargs):
		if args[0].linked:
			if os.path.exists(args[0].vsRepo):
				result = func(*args, **kargs)
				return result
			else:
				args[0].linked = False
				pm.error('[XGen Hub] : versionRepo path NOT exists. Process stopped.')
				return None
		else:
			pm.warning('[XGen Hub] : versionRepo not linked yet. Process stopped.')
			return None
	return deco

class MsXGenHub():
	"""docstring for ClassName"""
	def __init__(self):
		self.xgWork = xg.getProjectPath() + 'xgen/collections'
		self.anchor = xg.getProjectPath() + 'xgen/xgenRepo.anchor'
		self.linked = False
		self.vsRepoRaw = '${PROJECT}xgen/.version'
		self.vsRepo = ''
		# get versionRepo path from working anchor
		if os.path.isfile(self.anchor):
			with open(self.anchor) as anchor:
				content = anchor.readlines()
			self.vsRepo = content[-1]
		# check if versionRepo path is good
		if self.vsRepo and os.path.exists(self.vsRepo):
			self.linked = True
		else:
			pm.warning('[XGen Hub] : versionRepo not linked yet.')


	def initVersionRepo(self, repoProjPath):
		"""doc"""
		# Check versionRepo dir exists
		repoProjPath += '/' if not repoProjPath.endswith('/') else ''
		self.vsRepo = self.vsRepoRaw.replace('${PROJECT}', repoProjPath)
		if not os.path.exists(self.vsRepo):
			# Create versionRepo dir
			try:
				os.mkdir(self.vsRepo)
			except:
				print self.vsRepo
				raise
			# Hide it
			if os.name == 'nt':
				import ctypes
				FILE_ATTRIBUTE_HIDDEN = 0x02
				ctypes.windll.kernel32.SetFileAttributesW.argtypes = (ctypes.c_wchar_p, ctypes.c_uint32)
				ret = ctypes.windll.kernel32.SetFileAttributesW(self.vsRepo, FILE_ATTRIBUTE_HIDDEN)
				if not ret:
					raise ctypes.WinError()
		# write versionRepo anchor
		warnMsg = '\nDO NOT EDIT this file, unless you know what you\'re doing.\n'
		infoMsg = '\nThis anchor file keeps xgen versionRepo path at the last line.\n'
		content = ' !'*20 + warnMsg + ' !'*20 + infoMsg + self.vsRepo
		with open(self.anchor, 'w') as anchor:
			anchor.write(content)
		self.linked = True


	def paletteVerDir(self, palName, version, raw= None):
		"""doc"""
		return '/'.join([self.vsRepoRaw if raw else self.vsRepo, palName, version])


	def paletteWipDir(self, palName):
		"""doc"""
		return '/'.join([self.xgWork, palName])


	def refresh(self, level= ''):
		"""
		level: 'Full', 'Palette', 'Description'
		"""
		if level:
			de = xgg.DescriptionEditor
			if de != None:
				de.refresh(level)
		else:
			pm.refresh()


	def clearPreview(self):
		"""
		clear preview
		"""
		de = xgg.DescriptionEditor
		if de != None:
			de.clearMode = 2
			de.updateClearControls()
			de.clearPreview()


	def descControlMethod(self, palName, descName):
		"""
		Find out what instance method used by description to control primitives,
		and return type name:
			'Guides'
			'Attribute'
			'Groom'
		"""
		# check instance method
		primitive = xg.getActive(palName, descName, 'Primitive')
		if xg.getAttr('iMethod', palName, descName, primitive):
			return 'Guides'
		else:
			if xg.getAttr('groom', palName, descName):
				return 'Groom'
			else:
				return 'Attribute'
	
	@linkedCheck
	def snapshotImgPath(self, palName, version, index):
		"""doc"""
		imgName = '_'.join([palName, version, str(index)]) + '.jpg'
		imgPath = '/'.join([self.paletteVerDir(palName, version), '_snapshot_', imgName])
		return imgPath

	@linkedCheck
	def importPalette(self, palName, version, deltas= [], namespace= '', binding= False, copyMaps= False):
		"""
		** NOT SUPPORT NAMESPACE **
		Input var namespace was kept for future update.
		XGen palette will imported without validator.
		[!!!] When importing [BAKED] palette, @binding and @copyMaps set to False should be fine.
		"""
		xgenFileName = palName + '.xgen'
		xgenFile = '/'.join([self.paletteVerDir(palName, version), xgenFileName])
		if not os.path.isfile(xgenFile):
			pm.error('[XGen Hub] : .xgen file is not exists. -> ' + xgenFile)
			return None
		# IMPORT PALETTE
		palName = base.importPalette(xgenFile, deltas, namespace)
		# update the palette with the current project
		xg.setAttr('xgProjectPath', xg.getProjectPath(), palName)
		dataPath = xg.paletteRootVar() + '/' + palName
		xg.setAttr('xgDataPath', dataPath, palName)
		# create imported palette folder
		paletteRoot = xg.expandFilepath(dataPath, '', True, True)
		# create all imported descriptions folder
		msxg.setupDescriptionFolder(paletteRoot, palName)
		# wrap into maya nodes
		palName = str(pm.mel.xgmWrapXGen(pal= palName, wp= binding, wlg= binding, gi= binding))
		# copy maps from source
		if copyMaps:
			descNames = xg.descriptions(palName)
			uniqDescNames = descNames
			msxg.setupImportedMap(xgenFile, palName, descNames, uniqDescNames, namespace)
		# bind grooming descriptions to geometry
		if binding:
			for desc in descNames:
				igdesc = xg.getAttr('groom', palName, desc)
				if igdesc:
					# get groom dag node
					igdesc = xg.igActivateDescription(desc)
					# bind groom to geo
					pm.mel.igBindFromXGen(desc)
					# set groom density and sampling method
					pm.setAttr(igdesc + '.density', 50)
					pm.setAttr(igdesc + '.interpStyle', 1)
					# set all groom visible on
					xg.igSetDescriptionVisibility(True)
					# sync primitives tab attritube map path with auto export path
					xg.igSyncMaps(desc)

			# import grooming as well
			self.importGrooming(palName)

		return palName

	@linkedCheck
	def importDescription(self, palName, descName, version, binding= False):
		"""
		XGen description will imported without validator.
		When importing baked description, @binding set to False should be fine.
		"""
		xdscFileName = descName + '.xdsc'
		xdscFile = '/'.join([self.paletteVerDir(palName, version), descName, xdscFileName])
		if not os.path.isfile(xdscFile):
			pm.error('[XGen Hub] : .xdsc file is not exists. -> ' + xdscFile)
			return None
		desc = base.importDescription(palName, xdscFile)
		# create imported descriptions folder
		dataPath = xg.getAttr('xgDataPath', palName)
		paletteRoot = xg.expandFilepath(dataPath, '')
		msxg.setupDescriptionFolder(paletteRoot, palName, desc)
		# wrap into maya nodes
		pm.mel.xgmWrapXGen(pal= palName, d= desc, gi= binding)
		# bind to selected geometry
		if binding:
			igdesc = xg.getAttr('groom', palName, desc)
			xg.modifyFaceBinding(palName, desc, 'Append', '', False, len(igdesc))
			if igdesc:
				# set groom density and sampling method
				pm.setAttr(igdesc + '.density', 50)
				pm.setAttr(igdesc + '.interpStyle', 1)

			# import grooming as well
			self.importGrooming(palName, descName, version)
		# import guides as well
		self.importGuides(palName, descName, version)

		return desc

	@linkedCheck
	def importGrooming(self, palName, descName= None, version= None):
		"""
		"""
		if descName:
			descs = [descName]
		else:
			descs = xg.descriptions(palName)
		# copy groom dir from versionRepo if @version has given
		if version:
			# check exists
			groomDesc = {}
			hasMissing = False
			for desc in descs:
				if xg.getAttr('groom', palName, desc):
					groomSource = '/'.join([self.paletteVerDir(palName, version), desc, 'groom'])
					if os.path.exists(groomSource):
						groomDesc[desc] = groomSource
					else:
						hasMissing = True
						msg = '[XGen Hub] : palette [%s] description [%s] version [%s] NOT exists. -> %s'
						pm.warning(msg % (palName, desc, version, groomSource))
			# copy file if no missing
			if not hasMissing:
				for desc in groomDesc:
					src = groomDesc[desc]
					dst = '/'.join([self.paletteWipDir(palName), desc, 'groom'])
					dir_util.remove_tree(dst)
					dir_util.copy_tree(src, dst)
			else:
				pm.error('[XGen Hub] : Some data missing, Check ScriptEditor. grooming import stopped.')

				return None

		self.refresh()
		# IMPORT GROOMING
		# clear out autoExport path for preventing grooming auto export
		xg.setOptionVarString('igAutoExportFolder', '')
		for desc in descs:
			if xg.getAttr('groom', palName, desc):
				importPath = xg.expandFilepath('${DESC}/groom', desc)
				igDescr = xg.igDescription(desc)
				# import Attribute Map
				try:
					pm.waitCursor(state= True)
					pm.mel.iGroom(im= importPath, d= igDescr)
				finally:
					pm.waitCursor(state= False)
				# import Mask
				try:
					pm.waitCursor(state= True)
					pm.mel.iGroom(ik= importPath, d= igDescr)
				finally:
					pm.waitCursor(state= False)
				# import Region
				try:
					pm.waitCursor(state= True)
					pm.mel.iGroom(ir= importPath, d= igDescr)
				finally:
					pm.waitCursor(state= False)
		# restore default autoExport path
		xg.setOptionVarString('igAutoExportFolder', '${DESC}/groom')

		# IMPORT GROOM SETTINGS
		"""
		Currently only grab [density] setting,
		['length', 'width'] will messed up imported grooming's map attribute
		"""
		for desc in descs:
			igdesc = xg.getAttr('groom', palName, desc)
			jsonPath = xg.expandFilepath('${DESC}/groom', desc) + 'groomSettings.json'
			if igdesc and os.path.isfile(jsonPath):
				groomSettings = {}
				with open(jsonPath) as jsonFile:
					groomSettings = json.load(jsonFile)
				for key in groomSettings:
					# grab [density] setting only
					if key == 'density':
						pm.setAttr(igdesc + '.' + key, groomSettings[key])

		return True

	@linkedCheck
	def importGuides(self, palName, descName= None, version= None):
		"""
		"""
		if descName:
			descs = [descName]
		else:
			descs = xg.descriptions(palName)
		# copy groom dir from versionRepo if @version has given
		if version:
			# check exists
			guidesDesc = {}
			hasMissing = False
			for desc in descs:
				if self.descControlMethod(palName, desc) == 'Guides':
					abcPath = '/'.join([self.paletteVerDir(palName, version), desc, 'curves.abc'])
					if os.path.isfile(abcPath):
						guidesDesc[desc] = abcPath
					else:
						hasMissing = True
						msg = '[XGen Hub] : palette [%s] description [%s] version [%s] NOT exists. -> %s'
						pm.warning(msg % (palName, desc, version, abcPath))
			# copy file if no missing
			if not hasMissing:
				for desc in guidesDesc:
					src = guidesDesc[desc]
					dst = '/'.join([self.paletteWipDir(palName), desc, 'curves.abc'])
					os.remove(dst)
					shutil.copyfile(src, dst)
			else:
				pm.error('[XGen Hub] : Some .abc missing, Check ScriptEditor. guides import stopped.')

				return None

		# IMPORT GUIDES
		for desc in descs:
			# import alembic
			if not pm.pluginInfo('AbcImport', q= 1, l= 1):
				pm.loadPlugin('AbcImport')
			abcPath = xg.expandFilepath('${DESC}', desc) + 'curves.abc'
			if os.path.isfile(abcPath):
				pool = pm.group(em= 1, n= 'curvesToGuide_processPoll')
				pm.mel.AbcImport(abcPath, mode= 'import', rpr= pool)
				# select curves
				curves = pm.listRelatives(pool, c= 1)
				pm.select(curves, r= 1)
				# curvesToGuides
				pm.mel.xgmCurveToGuide(d= desc, tsp= 1.0, tsa= 0.0, deleteCurve= True)

		return True

	@linkedCheck
	def exportFullPackage(self, palName, version, bake= None):
		"""
		Export Palettes, Descriptions, Grooming, Guides, all together,
		even bake modifiers befoer export if needed.
		"""
		# change to export version path and keep current
		workPath = xg.getAttr('xgDataPath', palName)
		dataPath = self.paletteVerDir(palName, version, raw= True)
		xg.setAttr('xgDataPath', dataPath, palName)

		self.clearPreview()

		# bake modifiers
		if bake:
			for desc in xg.descriptions(palName):
				# bake Noise modifiers
				for fxm in xg.fxModules(palName, desc):
					if xg.fxModuleType(palName, desc, fxm) == 'NoiseFXModule':
						# temporarily turn off lod so we dont bake it in
						lod = xg.getAttr('lodFlag', palName, desc)
						xg.setAttr('lodFlag', 'false', palName, desc)
						# change mode to bake
						xg.setAttr('mode', '2', palName, desc, fxm)
						# bake the noise
						pm.mel.xgmNullRender(pb= desc)
						# restore
						xg.setAttr('lodFlag', lod, palName, desc)
						xg.setAttr('mode', '1', palName, desc, fxm)
				# bake groom modifiers
				fxm = xg.addFXModule(palName, desc, 'BakedGroomManagerFXModule')
				xg.setAttr('active', 'true', palName, desc, fxm)
				xg.bakedGroomManagerBake(palName, desc)
				# set Generator to XPD
				xg.setActive(palName, desc, 'FileGenerator')

		# export descriptions
		for desc in xg.descriptions(palName):
			expPath = xg.expandFilepath('${DESC}', desc, True, True) + desc + '.xdsc'
			xg.exportDescription(palName, desc, expPath)

		# export palettes
		expPath = dataPath + '/' + palName + '.xgen'
		xg.exportPalette(palName, expPath)

		# export grooming
		for desc in xg.descriptions(palName):
			igdesc = xg.getAttr('groom', palName, desc)
			if igdesc:
				expPath = xg.expandFilepath('${DESC}/groom', desc, True, True)
				tpu = 5
				sampling = 1
				igDescr = xg.igDescription(desc)
				# export Attribute Map
				try:
					pm.waitCursor(state= True)
					# may have .ptx file handle lock issue
					pm.mel.iGroom(exportMaps= expPath, texelsPerUnit= tpu,
						instanceMethod= sampling, description= igDescr)
				finally:
					pm.waitCursor(state= False)
				# export Mask
				try:
					pm.waitCursor(state= True)
					# may have .ptx file handle lock issue
					pm.mel.iGroom(exportMask= expPath, texelsPerUnit= tpu,
						description= igDescr)
				finally:
					pm.waitCursor(state= False)
				# export Region
				try:
					pm.waitCursor(state= True)
					# may have .ptx file handle lock issue
					pm.mel.iGroom(exportRegion= expPath, texelsPerUnit= tpu,
						description= igDescr)
				finally:
					pm.waitCursor(state= False)
				# export Settings
				jsonPath = expPath + 'groomSettings.json'
				groomSettings = {}.fromkeys(['density', 'length', 'width'])
				for key in groomSettings:
					groomSettings[key] = pm.getAttr(igdesc + '.' + key)
				with open(jsonPath, 'w') as jsonFile:
					json.dump(groomSettings, jsonFile, indent=4)

		# export guides
		with undoable('exportGuides'):
			for desc in xg.descriptions(palName):
				# listGuides
				guides = xg.descriptionGuides(desc)
				if not guides:
					continue
				expPath = xg.expandFilepath('${DESC}', desc)
				pm.select(guides, r= 1)
				# guides to curves
				curves = pm.mel.xgmCreateCurvesFromGuides(0, True)
				# export as alembic
				if not pm.pluginInfo('AbcExport', q= 1, l= 1):
					pm.loadPlugin('AbcExport')
				abcCmds = '-frameRange 1 1 -uvWrite -worldSpace -dataFormat ogawa '
				abcRoot = '-root ' + ' -root '.join([cur.longName() for cur in pm.ls(curves)])
				abcPath = expPath + 'curves.abc'
				pm.mel.AbcExport(j= abcCmds + abcRoot + ' -file ' + abcPath)
		pm.undo()

		# export snapshot
		for i in range(5):
			tmpPath = 'C:/temp/xgenHubSnap_' + str(i+1) + '.jpg'
			if os.path.isfile(tmpPath):
				imgPath = self.snapshotImgPath(palName, version, str(i+1))
				if not os.path.exists(os.path.dirname(imgPath)):
					os.mkdir(os.path.dirname(imgPath))
				shutil.move(tmpPath, imgPath)

		# restore dataPath
		xg.setAttr('xgDataPath', workPath, palName)

		self.refresh('Full')

		return True

@contextmanager
def undoable(name):
	try:
		pm.undoInfo(ock=True, cn=name)
		yield name
	except Exception, e:
		import traceback
		pm.warning('[XGen Hub] : Error while running undoable <%s> : %s' % (name, e))
		traceback.print_exc()
	finally:
		pm.undoInfo(cck=True)
