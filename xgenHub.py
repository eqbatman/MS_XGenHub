# -*- coding:utf-8 -*-
'''
Created on 2017.05.27

@author: davidpower

For implant versioning to our xgen workflow.

'''

import os, sys
import json
from contextlib import contextmanager
import shutil
import distutils.dir_util as dir_util
import pymel.core as pm
import xgenm as xg
import xgenm.xgGlobal as xgg
import xgenm.XgExternalAPI as base
import xgenm.xgCmds as xgcmds

import mXGen; reload(mXGen)
import mXGen.msxgmExternalAPI as msxgApi; reload(msxgApi)
import mXGen.msxgmAnimWireTool as msxgAwt; reload(msxgAwt)

import mMaya as mMaya; reload(mMaya)
import mMaya.mRender as mRender; reload(mRender)


__version__ = '1.1.0'


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
		self.xgWork = str(pm.workspace(q= 1, rd= 1)) + 'xgen/collections'
		self.anchor = str(pm.workspace(q= 1, rd= 1)) + 'xgen/xgenRepo.anchor'
		self.dirBake = 'vBaked'
		self.dirAnim = 'sim_'
		self.proxyPrefix = 'xgenHairProxy_'
		self.princPrefix = 'xgenHairPrinc_'
		self.xgShotAttr = 'custom_string_shotName'
		self.snapshotExt = '.bmp'
		self.snapshotTmp = 'C:/temp/xgenHubSnap_%d' + self.snapshotExt
		self.linked = False
		self.vsRepoRaw = '${PROJECT}xgen/.version'
		self.projPath = ''
		self.vsRepo = ''
		# get versionRepo path from working anchor
		if os.path.isfile(self.anchor):
			with open(self.anchor) as anchor:
				content = anchor.readlines()
			self.vsRepo = content[-1]
		# check if versionRepo path is good
		if self.vsRepo and os.path.exists(self.vsRepo):
			self.linked = True
			self.projPath = self.vsRepo.replace('xgen/.version', '')
			self.hatchScripts()
		else:
			pm.warning('[XGen Hub] : versionRepo not linked yet.')

		# check Vray plugin loaded
		if not pm.pluginInfo('vrayformaya', q= 1, l= 1):
			pm.loadPlugin('vrayformaya')
		if not pm.pluginInfo('xgenVRay', q= 1, l= 1):
			pm.loadPlugin('xgenVRay')
		# check xgen plug-in is loaded
		if not pm.pluginInfo('xgenToolkit', q= 1, l= 1):
			pm.loadPlugin('xgenToolkit')


	def initVersionRepo(self, repoProjPath):
		"""doc"""
		# Check versionRepo dir exists
		self.projPath = repoProjPath + '/' if not repoProjPath.endswith('/') else ''
		self.vsRepo = self.vsRepoRaw.replace('${PROJECT}', self.projPath)
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
		if not os.path.isdir(os.path.dirname(self.anchor)):
			os.makedirs(os.path.dirname(self.anchor))
		with open(self.anchor, 'w') as anchor:
			anchor.write(content)
		self.linked = True

		self.hatchScripts()


	def hatchScripts(self):
		"""doc"""
		scriptDir = pm.workspace.path + '/' + pm.workspace.fileRules['scripts']

		mVrsInitScript = '' \
		+ '# \n' \
		+ '# @author: davidpower\n' \
		+ '# \n' \
		+ '#  For V-Ray Post Translate Python Script\n' \
		+ '#  to import modules from scripts folder in the workspace on the fly\n' \
		+ '# \n' \
		+ 'import pymel.core as pm\n' \
		+ 'def getDaddy():\n' \
		+ '	vrsceneList = []; paletteList = []\n' \
		+ '	for dag in pm.ls("prefix*", typ= "transform"):\n' \
		+ '		if dag.hasAttr("vrscenePath"): vrsceneList.append(dag.getAttr("vrscenePath"))\n' \
		+ '		if dag.hasAttr("paletteName"): paletteList.append(dag.getAttr("paletteName"))\n' \
		+ '	return [vrsceneList, paletteList, "' + self.proxyPrefix + '", "' + self.princPrefix + '"]\n'

		mVrsInitScriptPath = scriptDir + '/mVrsInit.py'
		if not os.path.isfile(mVrsInitScriptPath):
			with open(mVrsInitScriptPath, 'w') as scriptFile:
				scriptFile.write(mVrsInitScript)

		mVRaySceneSrc = '/'.join([os.path.dirname(__file__), 'mVRay', 'mVRayScene.py'])
		mVRaySceneDst = scriptDir + '/mVRayScene.py'
		if not os.path.isfile(mVRaySceneDst) and os.path.isfile(mVRaySceneSrc):
			shutil.copyfile(mVRaySceneSrc, mVRaySceneDst)


	def paletteVerDir(self, palName, version, raw= None):
		"""doc"""
		return '/'.join([self.vsRepoRaw if raw else self.vsRepo, palName, version])


	def paletteDeltaDir(self, palName, version, shotName, raw= None):
		"""doc"""
		return '/'.join([self.vsRepoRaw if raw else self.vsRepo, palName, version, '_shot_', shotName])


	def paletteWipDir(self, palName):
		"""doc"""
		return '/'.join([self.xgWork, palName])


	def getVRaySceneFileRepo(self):
		"""doc"""
		return self.projPath + '/'.join(['renderData', 'xgen_vrscene'])


	def getVRaySceneFilePath(self, palName, shotName):
		"""doc"""
		return '/'.join([self.getVRaySceneFileRepo(), palName, shotName, palName + '.vrscene'])


	def getHairSysName(self, descName):
		"""doc"""
		return descName + '_hairSystem'


	def getRigidNameVar(self):
		"""doc"""
		return '%s_nRigid'


	def getAnimBranch(self, palName):
		"""doc"""
		return str(xg.getAttr('xgDogTag', palName))


	def getAnimShotName(self, palName):
		"""doc"""
		return str(xg.getAttr(self.xgShotAttr, palName))


	def getTimeSliderMinMax(self):
		"""doc"""
		start = int(pm.playbackOptions(q= 1, min= 1))
		end = int(pm.playbackOptions(q= 1, max= 1)) + 1
		return start, end


	def notifyMsg(self, msg, level):
		"""doc"""
		titleLevel = ['Notify', 'Warning', 'Error']
		iconLevel = ['information', 'warning', 'critical']
		msg = '[XGen Hub]	\n' + msg
		pm.confirmDialog(title= titleLevel[level], message= msg, ma= 'left',
			button= 'OK', icon= iconLevel[level])


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
			# stop auto update
			de.setPlayblast(False)
			de.updatePreviewControls()
			# clear all preview
			de.clearMode = 2
			de.updateClearControls()
			de.clearPreview()


	def xgOutputSettings(self, palName):
		"""doc"""
		for desc in xg.descriptions(palName):
			# set renderer
			xg.setAttr( 'renderer', 'VRay', palName, desc, 'RendermanRenderer')
			# auto set primitive Bound
			value = xgcmds.autoSetPrimitiveBound(palName, desc)
			#xg.setAttr('primitiveBound', value, palName, desc, 'RendermanRenderer')

		self.refresh('Full')


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
	def snapshotImgPath(self, palName, version, index, shotName= None):
		"""doc"""
		if shotName:
			imgName = '_'.join([palName, shotName, str(index)]) + self.snapshotExt
			imgPath = '/'.join([self.paletteDeltaDir(palName, version, shotName), '_snapshot_', imgName])
		else:
			imgName = '_'.join([palName, version, str(index)]) + self.snapshotExt
			imgPath = '/'.join([self.paletteVerDir(palName, version), '_snapshot_', imgName])
		return imgPath

	@linkedCheck
	def nDynPresetPath(self, palName, version):
		"""doc"""
		presetRepo = '/'.join([self.paletteVerDir(palName, version), '_nDynPresets_'])
		return presetRepo

	@linkedCheck
	def importPalette(self, palName, version, binding= False, anim= False, asDelta= False, delta= []):
		"""
		** NOT SUPPORT NAMESPACE **
		XGen palette will imported without validator.
		[!!!] When importing [BAKED] palette, @binding set to False should be fine.
		"""
		xgenFileName = palName + '.xgen'
		xgenFile = str('/'.join([self.paletteVerDir(palName, version), xgenFileName]))
		if not os.path.isfile(xgenFile):
			pm.error('[XGen Hub] : .xgen file is not exists. -> ' + xgenFile)
			return None
		if asDelta and not pm.sceneName():
			pm.error('[XGen Hub] : Current scene is not saved (), please save first.')
			return None
		
		self.clearPreview()
		
		# check if palette exists in current scene
		if palName in xg.palettes():
			# delete current palette folder
			palDir = xg.expandFilepath(xg.getAttr('xgDataPath', palName), '')
			if os.path.isdir(palDir):
				dir_util.remove_tree(palDir)
			# delete current palette
			# this action might cry about 'None type object has no attr "previewer"'
			# when there is no xgen ui panel
			xg.deletePalette(palName)
		
		# IMPORT PALETTE
		palName = base.importPalette(xgenFile, delta, '')
		# update the palette with the current project
		xg.setAttr('xgProjectPath', str(pm.workspace(q= 1, rd= 1)), palName)
		dataPath = xg.paletteRootVar() + '/' + palName
		xg.setAttr('xgDataPath', dataPath, palName)
		# create imported palette folder
		paletteRoot = xg.expandFilepath(dataPath, '', True, True)
		# create all imported descriptions folder
		msxgApi.setupDescriptionFolder(paletteRoot, palName)
		# wrap into maya nodes
		palName = str(pm.mel.xgmWrapXGen(pal= palName, wp= binding, wlg= binding, gi= binding))
		# copy maps from source
		descNames = xg.descriptions(palName)
		msxgApi.setupImportedMap(xgenFile, palName, descNames, self.projPath)
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
					pm.setAttr(igdesc + '.density', 1)
					pm.setAttr(igdesc + '.interpStyle', 1)
					# set all groom visible on
					xg.igSetDescriptionVisibility(True)
					# sync primitives tab attritube map path with auto export path
					xg.igSyncMaps(desc)

			# import grooming as well
			self.importGrooming(palName)

		# import as anim, build hairSystem
		if anim:
			# build hairSystem
			self.linkHairSystem(palName)
			# check preset dir exists
			presetLocalDir = str(pm.internalVar(userPresetsDir= 1))
			presetRepo = self.nDynPresetPath(palName, version)
			if os.path.exists(presetRepo):
				# copy preset
				for prs in os.listdir(presetRepo):
					dstPath = presetLocalDir + prs
					prs = '/'.join([presetRepo, prs])
					shutil.copyfile(prs, dstPath)
				# load preset
				# [note] nucleus preset will not be loaded during current devlope
				presetMel = []
				for nodeType in ['hairSystem', 'nRigid']:
					presetDict = self.ioAttrPreset(nodeType, False)
					presetMel.extend(presetDict.values())
				# dump preset
				for prs in presetMel:
					os.remove(prs)
			else:
				pm.warning('[XGen Hub] : nDynamic attribute presets folder not found.')

		if asDelta:
			dataPath = xg.getAttr('xgDataPath', palName)
			dataPath = dataPath + ';' + self.paletteVerDir(palName, version, raw= True)
			xg.setAttr('xgDataPath', dataPath, palName)
			# save scenes
			pm.saveFile(f= 1)
			# set export delta
			pm.setAttr(palName + '.xgExportAsDelta', 1)

		self.notifyMsg('Collection Import Complete !', 0)

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

		self.clearPreview()

		# check if descriptions exists in current scene
		if descName in xg.descriptions(palName):
			# delete current description folder
			descDir = xg.expandFilepath('${DESC}', descName)
			if os.path.isdir(descDir):
				dir_util.remove_tree(descDir)
			# delete current description
			xg.deleteDescription(palName, descName)
		# IMPORT DESCRIPTION
		desc = base.importDescription(palName, xdscFile)
		# create imported descriptions folder
		dataPath = xg.getAttr('xgDataPath', palName)
		paletteRoot = xg.expandFilepath(dataPath, '')
		msxgApi.setupDescriptionFolder(paletteRoot, palName, desc)
		# wrap into maya nodes
		pm.mel.xgmWrapXGen(pal= palName, d= desc, gi= binding)
		# bind to selected geometry
		if binding:
			igdesc = xg.getAttr('groom', palName, desc)
			xg.modifyFaceBinding(palName, desc, 'Append', '', False, len(igdesc))
			if igdesc:
				# set groom density and sampling method
				pm.setAttr(igdesc + '.density', 1)
				pm.setAttr(igdesc + '.interpStyle', 1)

			# import grooming as well
			self.importGrooming(palName, descName, version)
		# import guides as well
		self.importGuides(palName, descName, version)

		self.notifyMsg('Description Import Complete !', 0)

		return desc

	@linkedCheck
	def importGrooming(self, palName, descName= None, version= None):
		"""
		"""
		self.clearPreview()

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
					if os.path.isdir(dst):
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

		self.notifyMsg('Grooming Import Complete !', 0)

		return True

	@linkedCheck
	def importGuides(self, palName, descName= None, version= None):
		"""
		"""
		self.clearPreview()

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
					if os.path.isdir(dst):
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

		self.notifyMsg('Guides Import Complete !', 0)

		return True

	@linkedCheck
	def importAnimResult(self, palName, version, shotName):
		"""
		"""
		self.clearPreview()

		# get delta .xgd file
		deltaPath = self.paletteDeltaDir(palName, version, shotName)
		deltaFile = '/'.join([deltaPath, palName + '.xgd'])

		# import
		self.importPalette(palName, version, False, False, True, [deltaFile])

		# get wires.abc
		wiresAbc = {}
		for abc in os.listdir(deltaPath):
			abcPath = '/'.join([deltaPath, abc])
			if os.path.isfile(abcPath):
				descName = abc.split('.')[0]
				wiresAbc[descName] = str(abcPath)
		# animWire turn off live mode to read .abc
		for desc in [desc for desc in wiresAbc if desc in xg.descriptions(palName)]:
			for fxm in [fxm for fxm in xg.fxModules(palName, desc) if xg.fxModuleType(palName, desc, fxm) == 'AnimWiresFXModule']:
				if xg.getAttr('active', palName, desc, fxm) == 'true':
					xg.setAttr('liveMode', 'false', palName, desc, fxm)
					xg.setAttr('wiresFile', wiresAbc[desc], palName, desc, fxm)

		# assign shaders

		# render settings
		self.xgOutputSettings(palName)

		self.refresh('Full')

		self.notifyMsg('Anim Result Import Complete !', 0)

		return True

	@linkedCheck
	def connectVRayScene(self, palName, shotName):
		"""doc"""
		renderGlob = pm.PyNode('defaultRenderGlobals')
		if not renderGlob.currentRenderer.get() == 'vray':
			self.notifyMsg('Current Renderer is Not V-Ray !', 2)
			return None

		# hatch prxoy cube
		proxyNodeName = self.proxyPrefix + palName
		if pm.PyNode(proxyNodeName):
			pm.delete(pm.PyNode(proxyNodeName))
		customAttrs = {
			'vrscenePath': self.getVRaySceneFilePath(palName, shotName),
			'paletteName': palName,
			}
		prxoy = pm.polyCube(n= proxyNodeName, ch= False)[0]
		for attr in customAttrs:
			prxoy.addAttr(attr, dataType= 'string', k= False)
			prxoy.setAttr(attr, str(customAttrs[attr]), l= True)

		# hatch mel render callback
		vrsCallback = 'python("import mVrsInit;yourDaddy=mVrsInit.getDaddy()")'
		melCallback = renderGlob.preMel.get()
		if not vrsCallback in melCallback: renderGlob.preMel.set(melCallback + ';' + vrsCallback)

		# make script
		scriptContent = [
			'# [ XGen Hub ] Start #',
			'# Please Do Not Edit #',
			'import mVRayScene',
			'mVRayScene.kickProxyOutWith(yourDaddy)',
			'# [ XGen Hub ]  End #'
			]
		# get postScript
		vraySet = mRender.getVRaySettingsNode()
		postScript = vraySet.postTranslatePython.get()
		# check if there are already have we generated script
		if not scriptContent[0] in postScript: postScript = '\n'.join([postScript].extend(scriptContent))
		# set postScript
		vraySet.postTranslatePython.set(postScript)

		return True

	@linkedCheck
	def exportFullPackage(self, palName, version, bake= False, anim= False):
		"""
		Export Palettes, Descriptions, Grooming, Guides, all together,
		even bake modifiers befoer export if needed.
		"""
		self.clearPreview()
		
		# bake modifiers
		generator = {}
		if bake:
			for desc in xg.descriptions(palName):
				# bake Noise modifiers
				for fxm in xg.fxModules(palName, desc):
					if xg.fxModuleType(palName, desc, fxm) == 'ClumpingFXModule':
						# set cvAttr to True, for anim modifiers which needs clump
						xg.setAttr('cvAttr', 'true', palName, desc, fxm)
					if xg.fxModuleType(palName, desc, fxm) == 'NoiseFXModule':
						# temporarily turn off lod so we dont bake it in
						lod = xg.getAttr('lodFlag', palName, desc)
						xg.setAttr('lodFlag', 'false', palName, desc)
						# change mode for bake
						xg.setAttr('mode', '2', palName, desc, fxm)
						# bake the noise
						pm.mel.xgmNullRender(pb= desc)
						# restore
						xg.setAttr('lodFlag', lod, palName, desc)
						# change mode to baked
						xg.setAttr('mode', '1', palName, desc, fxm)
				# bake groom modifiers
				fxm = xg.addFXModule(palName, desc, 'BakedGroomManagerFXModule')
				xg.setAttr('active', 'true', palName, desc, fxm)
				xg.bakedGroomManagerBake(palName, desc)
				# set Generator to XPD
				generator[desc] = xg.getActive(palName, desc, 'Generator')
				xg.setActive(palName, desc, 'FileGenerator')
		
		# change to export version path and keep current
		workPath = xg.getAttr('xgDataPath', palName)
		workProj = xg.getAttr('xgProjectPath', palName)
		xg.setAttr('xgDataPath', self.paletteVerDir(palName, version, raw= True), palName)
		xg.setAttr('xgProjectPath', self.projPath, palName)
		# get resolved repo path
		dataPath = self.paletteVerDir(palName, version)

		# set [xgDogTag] attr for ANIM record branchName
		if anim:
			xg.setAttr('xgDogTag', version, palName)

		# export descriptions
		for desc in xg.descriptions(palName):
			dstDescDir = xg.expandFilepath('${DESC}', desc, True, True)
			expPath = dstDescDir + desc + '.xdsc'
			xg.exportDescription(palName, desc, expPath)
			# copy map files
			srcDescVar = workPath.replace('${PROJECT}', workProj) + '/${DESC}'
			srcDescDir = xg.expandFilepath(srcDescVar, desc)
			for mapDir in os.listdir(srcDescDir):
				srcMap = os.path.join(srcDescDir, mapDir)
				dstMap = os.path.join(dstDescDir, mapDir)
				if os.path.isdir(srcMap):
					dir_util.copy_tree(srcMap, dstMap)

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

		if anim:
			# save out hairSystem preset
			presetMel = []
			for nodeType in ['nucleus', 'hairSystem', 'nRigid']:
				presetDict = self.ioAttrPreset(nodeType, True)
				presetMel.extend(presetDict.values())
			# move preset file to version repo
			presetRepo = self.nDynPresetPath(palName, version)
			if not os.path.exists(presetRepo):
				os.mkdir(presetRepo)
			for prs in presetMel:
				dstPath = '/'.join([presetRepo, os.path.basename(prs)])
				shutil.move(prs, dstPath)
			# create empty _shot_ folder
			shotDir = self.paletteDeltaDir(palName, version, '')
			if not os.path.exists(shotDir):
				os.mkdir(shotDir)

		# export snapshot
		for i in range(5):
			tmpPath = self.snapshotTmp % (i+1)
			if os.path.isfile(tmpPath):
				imgPath = self.snapshotImgPath(palName, version, str(i+1))
				if not os.path.exists(os.path.dirname(imgPath)):
					os.mkdir(os.path.dirname(imgPath))
				shutil.move(tmpPath, imgPath)

		# restore dataPath
		xg.setAttr('xgDataPath', workPath, palName)
		xg.setAttr('xgProjectPath', workProj, palName)

		# restore modifiers
		if bake:
			for desc in xg.descriptions(palName):
				# bake Noise modifiers
				for fxm in xg.fxModules(palName, desc):
					if xg.fxModuleType(palName, desc, fxm) == 'NoiseFXModule':
						# restore to live mode
						xg.setAttr('mode', '0', palName, desc, fxm)
				# remove bake groom modifiers
				for fxm in xg.fxModules(palName, desc):
					if xg.fxModuleType(palName, desc, fxm) == 'BakedGroomManagerFXModule':
						xg.removeFXModule(palName, desc, fxm)
				# restore Generator
				xg.setActive(palName, desc, generator[desc])

		self.refresh('Full')

		self.notifyMsg('Collection Export Complete !', 0)

		return True

	@linkedCheck
	def exportAnimPackage(self, palName, shotName):
		"""doc"""
		# get version info from [xgDogTag]
		version = self.getAnimBranch(palName)
		if not version:
			pm.error('[XGen Hub] : Couldn\'t get ANIM branch name. Export process stop.')
			return None

		self.clearPreview()

		# add shotName attribute to xgen and save in xgen delta later
		if not xg.attrExists(self.xgShotAttr, palName):
			xg.addCustomAttr(self.xgShotAttr, palName)
		xg.setAttr(self.xgShotAttr, shotName, palName)
		
		# get resolved repo shotName path
		deltaPath = self.paletteDeltaDir(palName, version, shotName)
		if not os.path.exists(deltaPath):
			os.mkdir(deltaPath)
		
		deltaFile = '/'.join([deltaPath, palName + '.xgd'])

		# export delta
		xg.createDelta(palName, deltaFile)

		# get curves and export
		for desc in xg.descriptions(palName):
			curvesGrp = pm.ls(desc + '_hairSystemOutputCurves', type= 'transform')
			if curvesGrp and curvesGrp[0].listRelatives():
				curves = curvesGrp[0].listRelatives()
				# cache curves, export as alembic
				if not pm.pluginInfo('AbcExport', q= 1, l= 1):
					pm.loadPlugin('AbcExport')
				start, end = self.getTimeSliderMinMax()
				abcCmds = '-frameRange %d %d -uvWrite -worldSpace -dataFormat ogawa ' % (start, end)
				abcRoot = '-root ' + ' -root '.join([cur.longName() for cur in pm.ls(curves)])
				abcPath = '/'.join([deltaPath, desc + '.abc'])
				pm.mel.AbcExport(j= abcCmds + abcRoot + ' -file ' + abcPath)

		# export snapshot
		for i in range(5):
			tmpPath = self.snapshotTmp % (i+1)
			if os.path.isfile(tmpPath):
				imgPath = self.snapshotImgPath(palName, version, str(i+1), shotName)
				if not os.path.exists(os.path.dirname(imgPath)):
					os.mkdir(os.path.dirname(imgPath))
				shutil.move(tmpPath, imgPath)

		self.refresh('Full')

		self.notifyMsg('Anim Result Export Complete !', 0)

		return True

	@linkedCheck
	def exportVRaySceneFile(self, palName):
		"""doc"""
		version = self.getAnimBranch(palName)
		if not version:
			pm.error('[XGen Hub] : Couldn\'t get ANIM branch name. Export process stop.')
			return None
		shotName = self.getAnimShotName(palName)
		if not shotName:
			pm.error('[XGen Hub] : Couldn\'t get ANIM shotName. Export process stop.')
			return None

		# hide everything (root nodes in outliner)
		pm.hide(all= 1)
		# show xgen palette
		pm.setAttr(palName + '.v', True)
		# get start, end frame from time slider
		start, end = self.getTimeSliderMinMax()
		# set renderer to VRay and time range
		renderGlob = pm.PyNode('defaultRenderGlobals')
		renderGlob.currentRenderer.set('vray')
		renderGlob.startFrame.set(start)
		renderGlob.endFrame.set(end)
		renderGlob.byFrameStep.set(1)
		# setup vray render settings
		vrsceneFile = self.getVRaySceneFilePath(palName, shotName)
		vraySet = mRender.getVRaySettingsNode()
		vrayAttrs = {
			'vrscene_render_on': 0,
			'vrscene_on': 1,
			'misc_separateFiles': 1,
			'misc_exportLights': 0,
			'misc_exportNodes': 1,
			'misc_exportGeometry': 1,
			'misc_exportMaterials': 1,
			'misc_exportTextures': 1,
			'misc_exportBitmaps': 0,
			'misc_eachFrameInFile': 0,
			'misc_meshAsHex': 1,
			'misc_transformAsHex': 1,
			'misc_compressedVrscene': 1,
			'vrscene_filename': vrsceneFile,
			'animType': 1,
			'animBatchOnly': 0,
			'runToAnimationStart': 0,
			'runToCurrentTime': 0
		}
		for attr in vrayAttrs:
			vraySet.setAttr(attr, vrayAttrs[attr])
		# hit render
		pm.mel.RenderIntoNewWindow()
		# modify .vrscene file
		content = ''
		vrscene = open(vrsceneFile, 'r')
		for _ in " "*7: content += vrscene.readline()
		vrscene.close()
		include = '#include "%s_%s.vrscene"\n'
		vrsType = ['nodes', 'geometry', 'materials', 'textures']
		for vt in vrsType:
			content += include % (vrsceneFile.split('.')[0], vt)
		with open(vrsceneFile, 'w') as vrscene:
			vrscene.write(content)

		self.notifyMsg('File .vrscene Export Complete !', 0)

		return True


	def linkHairSystem(self, palName):
		"""doc"""
		self.clearPreview()

		nHairAttrs = {
			'noStretch': 1,
			'stretchResistance': 100,
			'compressionResistance': 100,
			'startCurveAttract': 0.3,
			'mass': 0.05
			}

		# get active AnimWire module list
		animWireDict = {}
		for desc in xg.descriptions(palName):
			for fxm in xg.fxModules(palName, desc):
				if xg.fxModuleType(palName, desc, fxm) == 'AnimWiresFXModule':
					if xg.getAttr('active', palName, desc, fxm) == 'true':
						hsysName = self.getHairSysName(desc)
						hsysTransforms = [str(hsys.getParent().name()) for hsys in pm.ls(type= 'hairSystem')]
						if hsysName in hsysTransforms:
							pm.warning('[XGen Hub] : description: %s has hairSystem [%s], skipped.' % (desc, hsysName))
						else:
							animWireDict[desc] = fxm
		# build hairSystem
		for desc in animWireDict:
			fxm = animWireDict[desc]
			pm.warning('[XGen Hub] : Building hairSystem for description: %s, FXModule: %s' % (desc, fxm))
			descHairSysName = self.getHairSysName(desc)
			msxgAwt.exportCurvesMel(palName, desc, fxm)
			meshPatch, hsys = msxgAwt.xgmMakeCurvesDynamic(descHairSysName, False)
			msxgAwt.nRigidRename(meshPatch, self.getRigidNameVar())
			msxgAwt.attachSlot(palName, desc, fxm, descHairSysName)
			pm.warning('[XGen Hub] : Link hairSystem done.')
			# set some attributes
			for attr in nHairAttrs:
				hsys.setAttr(attr, nHairAttrs[attr])


	def ioAttrPreset(self, nodeType, save):
		"""doc"""
		presetLocalDir = str(pm.internalVar(userPresetsDir= 1))
		presetVar = presetLocalDir + '%sPreset_%s.mel'
		# save out presets
		presetDict = {}
		for node in pm.ls(type= nodeType):
			presetName = node.name()
			if save:
				pm.nodePreset(save= [node, presetName])
			else:
				pm.nodePreset(load= [node, presetName])
			presetDict[node.name()] = presetVar % (nodeType, presetName)

		return presetDict



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
