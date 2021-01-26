'''
one executable to catalogs from data from a single tile
'''



#standard python
import sys
import os
import shutil
import unittest
from datetime import datetime
import json
import numpy as np
import fitsio
import glob
import argparse
from astropy.table import Table,join,unique,vstack
from matplotlib import pyplot as plt

sys.path.append('../py') #this requires running from LSS/bin, *something* must allow linking without this but is not present in code yet

#from this package
try:
    import LSS.mkCat_singletile.cattools as ct
except:
    print('import of LSS.mkCat_singletile.cattools failed')
    print('are you in LSS/bin?, if not, that is probably why the import failed')   
import LSS.mkCat_singletile.fa4lsscat as fa
import LSS.mkCat_singletile.xitools as xt


parser = argparse.ArgumentParser()
parser.add_argument("--type", help="tracer type to be selected")
parser.add_argument("--tile", help="observed tile to use")
parser.add_argument("--night", help="date of observation")
parser.add_argument("--fadate", help="date for fiberassign run")
parser.add_argument("--basedir", help="base directory for output, default is CSCRATCH",default=os.environ['CSCRATCH'])
parser.add_argument("--release", help="version of the spectroscopic pipeline",default='blanc')
parser.add_argument("--version", help="catalog version; use 'test' unless you know what you are doing!",default='test')
args = parser.parse_args()
print(args)

type = args.type
tile = args.tile
night = args.night
fadate = args.fadate
basedir = args.basedir
release = args.release
version = args.version

#make directories used in directory tree

if not os.path.exists(basedir):
    print('!!!the base directory does not exist!!! ALL WILL FAIL')

if not os.path.exists(basedir+'/SV1'):
    os.mkdir(basedir+'/SV1')
    print('made '+basedir+'/SV1')
    
svdir = basedir+'/SV1/LSS/'

if not os.path.exists(svdir):
    os.mkdir(svdir)
    print('made '+svdir)
    
if not os.path.exists(svdir+'/logs'):
    os.mkdir(svdir+'/logs')
    print('made '+svdir+'/logs')

if not os.path.exists(svdir+'/LSScats'):
    os.mkdir(svdir+'/LSScats')
    print('made '+svdir+'/LSScats')

dirout = svdir+'LSScats/'+version+'/'
if not os.path.exists(dirout):
    os.mkdir(dirout)
    print('made '+dirout)

#set up log file
logfn = svdir + '/logs/log'+datetime.now().isoformat()+'.txt'
logf = open(logfn,'w')
print('a log of what was run is going to '+logfn)

logf.write('running mkCat_singletile.py from '+os.getcwd()+'\n\n')
logf.write('arguments were:\n')
logf.write(str(args)+'\n')

#random directories + info into log file    
randir = svdir+'random'
rm = 0
rx = 10
logf.write('using random files '+str(rm)+ ' through '+str(rx)+' (this is python, so max is not inclusive)\n')
for i in range(rm,rx):
    if not os.path.exists(svdir+'random'+str(i)):
        os.mkdir(svdir+'random'+str(i))
        print('made '+str(i)+' random directory')

from desitarget.sv1 import sv1_targetmask
tarbit = int(np.log2(sv1_targetmask.desi_mask[type]))

pr = 10000

if type[:3] == 'LRG':
    #tarbit = 0 #targeting bit
    pr = 3200 #priority; anything with higher priority vetos fiber in randoms
if type[:3] == 'QSO':
    #tarbit = 2
    pr = 3400
if type[:3] == 'ELG':
    #tarbit = 1
    pr = 3000


print(type,tile,night,pr)
tp = 'SV1_DESI_TARGET'
print('targeting bit, priority, target type; CHECK THEY ARE CORRECT!')
print(tarbit,pr,tp)

#where to find input data
fadir = '/global/cfs/cdirs/desi/survey/fiberassign/SV1/'+fadate+'/'
tardir = fadir
coaddir = '/global/cfs/cdirs/desi/spectro/redux/'+release+'/tiles/'

mtlf = fadir+'/0'+tile+'-targ.fits' #mtl file that was input to fiberassign
print('using '+mtlf +' as the mtl file; IS THAT CORRECT?')
tilef = fadir+'0'+tile+'-tiles.fits' #the tile file
fbaf = fadir+'fba-0'+tile+'.fits' #the fiberassign file

#output files for the data (randoms defined below since there are 10 of them)
ffd = dirout+type+str(tile)+'_'+night+'_full.dat.fits'
fcd = dirout+type+str(tile)+'_'+night+'_clustering.dat.fits'


elgandlrgbits = [1,5,6,7,8,9,11,12,13] #these get used to veto imaging area
logf.write('imaging mask bits applied are '+str(elgandlrgbits)+'\n') 

zfailmd = 'zwarn' #only option so far, but can easily add things based on delta_chi2 or whatever
weightmd = 'wloc' #only option so far, weight observed redshifts by number of targets that wanted fiber

mkranmtl = False #make a mtl file of randoms, this is what takes the longest, make sure toggle to false once done
runrfa = False #run randoms through fiberassign
mkfulld = True #make the 'full' catalog containing info on everything physically reachable by a fiber
mkfullr = True #make the random files associated with the full data files
mkclus = True #make the data/random clustering files; these are cut to a small subset of columns
docatplots = False #produce some validation plots
doclus = True #get paircounts, only works for AJR
mknz = True #get n(z) for type and all subtypes


if mkranmtl: #this cuts the random file to the tile and adds columns necessary for fiberassign, done here it is very inefficient (would be better to do all tiles at once)
    for i in range(rm,rx):
        ct.randomtilesi(tilef ,randir,i)
    logf.write('made per random mtl files cut to tile area\n')

if runrfa:
    fbah = fitsio.read_header(fbaf)
    dt = fbah['FA_RUN']
    for i in range(rm,rx):
        fa.getfatiles(randir+str(i)+'/tilenofa-'+str(tile)+'.fits',tilef,dirout=randir+str(i)+'/',dt = dt)
    logf.write('put randoms through fiberassign\n')

if mkfulld:
    tspec = ct.combspecdata(tile,night,coaddir)
    pdict,goodloc = ct.goodlocdict(tspec)
    tfa = ct.gettarinfo_type(fadir,tile,goodloc,mtlf,tarbit,tp=tp)
    print(tspec.dtype.names)
    tout = join(tfa,tspec,keys=['TARGETID','LOCATION','PRIORITY'],join_type='left') #targetid should be enough, but all three are in both and should be the same
    print(tout.dtype.names)
    wz = tout['ZWARN']*0 == 0
    wzg = tout['ZWARN'] == 0
    print('there are '+str(len(tout[wz]))+' rows with spec obs redshifts and '+str(len(tout[wzg]))+' with zwarn=0')
        
    tout.write(ffd,format='fits', overwrite=True) 
    print('wrote matched targets/redshifts to '+ffd)
    logf.write('made full data files\n')
    
if mkfullr:
    tspec = ct.combspecdata(tile,night,coaddir)
    pdict,goodloc = ct.goodlocdict(tspec)
    for i in range(rm,rx):
        ranall = ct.mkfullran(tile,goodloc,pdict,randir+str(i)+'/')
        #fout = dirout+type+str(tile)+'_'+night+'_full.ran.fits'
        ffr = dirout+type+str(tile)+'_'+night+'_'+str(i)+'_full.ran.fits'
        ranall.write(ffr,format='fits', overwrite=True)
    logf.write('made full random files\n')

if mkclus:
    maxp,loc_fail = ct.mkclusdat(ffd,fcd,zfailmd,weightmd,maskbits=elgandlrgbits)    
    for i in range(rm,rx):
        ffr = dirout+type+str(tile)+'_'+night+'_'+str(i)+'_full.ran.fits'
        fcr = dirout+type+str(tile)+'_'+night+'_'+str(i)+'_clustering.ran.fits'      
        ct.mkclusran(ffr,fcr,fcd,maxp,loc_fail,maskbits=elgandlrgbits)
    logf.write('made clustering data and random files\n')

if mknz:
    subts = ['LRG','ELG','QSO','LRG_IR','LRG_OPT','LRG_SV_OPT','LRG_SV_IR','ELG_SV_GTOT','ELG_SV_GFIB','ELG_FDR_GTOT','ELG_FDR_GFIB','QSO_COLOR_4PASS',\
    'QSO_RF_4PASS','QSO_COLOR_8PASS','QSO_RF_8PASS']
    subtl = []
    for subt in subts:
        if subt[:3] == type:
            subtl.append(subt)
    print(subtl)
    fcr = dirout+type+str(tile)+'_'+night+'_0_clustering.ran.fits'
    for subt in subtl:
        fout = dirout+subt+str(tile)+'_'+night+'_nz.dat'
        ct.mknz(ffd,fcd,fcr,subt,fout)
    logf.write('made n(z) for type and all subtypes\n')

if docatplots:
    ii = 0
    fd = fitsio.read(ffd)
    plt.plot(fd['RA'],fd['DEC'],'r.',label='potential targets')
    fc = fitsio.read(fcd)
    plt.plot(fc['RA'],fc['DEC'],'bo',label='good redshifts')
    ffr = fitsio.read(dirout+type+str(tile)+'_'+night+'_'+str(ii)+'_clustering.ran.fits')
    plt.plot(ffr['RA'],ffr['DEC'],'k,',label='randoms')

    plt.xlabel('RA')
    plt.ylabel('DEC')
    plt.title(type+' on tile '+tile+' observed '+night)
    plt.legend()
    plt.show()
    if type == 'ELG':
        zr = (.3,2)
    if type == 'LRG':
        zr = (.4,1.7)
    if type == 'QSO':
        zr = (.1,4.5)    
    plt.hist(fc['Z'],bins=100,range=zr,histtype='step')
    plt.xlabel('redshift')
    plt.ylabel('# with zwarn == 0')
    plt.title(type+' on tile '+tile+' observed '+night)
    plt.show()

if doclus:
	import subprocess
	dirpcadw = os.environ['CSCRATCH']+'/pcadw/'
	dirpc = os.environ['CSCRATCH']+'/paircounts/'
	if not os.path.exists(dirpc):
		os.mkdir(dirpcadw)
	if not os.path.exists(dirpc):
		os.mkdir(dirpc)

	if type[:3] == 'ELG':
		zmin = .8
		zmax = 1.6
	if type == 'LRG':
		zmin = .5
		zmax = 1.1
	if type == 'QSO':
		zmin = 1.
		zmax = 2.

	rmax = 10
	gf = xt.createSourcesrd_ad(type,tile,night,zmin=zmin,zmax=zmax,datadir=dirout)
	subprocess.run(['chmod','+x','dopc'+gf+'.sh'])
	subprocess.run('./dopc'+gf+'.sh')
	for i in range(rm+1,rmax):
		gf = xt.createSourcesrd_ari(type,tile,night,i,zmin=zmin,zmax=zmax,datadir=dirout)
		subprocess.run(['chmod','+x','dopc'+gf+'.sh'])
		subprocess.run('./dopc'+gf+'.sh')
	xt.ppxilcalc_LSDfjack_bs(type,tile,night,zmin=zmin,zmax=zmax,nran=rmax)
	xt.ppxilcalc_LSDfjack_bs(type,tile,night,zmin=zmin,zmax=zmax,bs=5,nran=rmax)
	logf.write('computed paircounts\n')
        
# 
# dr = fitsio.read(rf)
# drm = cutphotmask(dr)
# 
# wpr = drm['PRIORITY'] <= maxp
# wzf = np.isin(drm['LOCATION'],loc_fail)
# wzt = wpr & ~wzf
# 
# drmz = drm[wzt]
# print(str(len(drmz))+' after cutting based on failures and priority')
# plt.plot(drmz['RA'],drmz['DEC'],'k,')
# plt.plot(drm[~wpr]['RA'],drm[~wpr]['DEC'],'b,')
# plt.plot(drm[wzf]['RA'],drm[wzf]['DEC'],'g,')
# plt.plot(ddclus['RA'],ddclus['DEC'],'r.')
# plt.show()
# rclus = Table()
# rclus['RA'] = drmz['RA']
# rclus['DEC'] = drmz['DEC']
# rclus['Z'] = drmz['Z']
# rclus['WEIGHT'] = np.ones(len(drmz))
# 
# rclus.write(rfout,format='fits',overwrite=True)

