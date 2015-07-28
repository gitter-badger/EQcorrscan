#!/usr/bin/python
"""
Script to re-gernate templates from the originally defined templates of varying
lengths, and enable stacking.
"""
import glob, os
templates=glob.glob('templates/*.ms')
datasource='/Volumes/GeoPhysics_09/users-data/chambeca/SAMBA_archive/day_volumes_S/'
GeoNet='/Volumes/GeoPhysics_09/users-data/chambeca/Alpine_Fault_SAC/SAC_resampled/'
length1=3.0
length2=6.0
out2='templates/6sec_templates'
length3=12.0
out3='templates/12sec_templates'
# Lengths in seconds, length1 should be the original length
# Lengths will be generated by ading extra data in equal amounts to the front
# and back of templates

from obspy import read, Stream
from utils import clustering, stacking
from par import template_gen_par as defaults
from core import template_gen
from utils.Sfile_util import PICK
import numpy as np
import matplotlib.pyplot as plt

templates.sort()
f=open('regen_template.err','w')
for tfile in templates:
    # Check to see if the work has already been done
    if glob.glob(out2+'/'+tfile.split('/')[-1]) and \
       glob.glob(out3+'/'+tfile.split('/')[-1]):
        print 'Already worked on: '+tfile.split('/')[-1]
        continue
    template=read(tfile)
    picks=[]
    if 'original_data' in locals():
        del original_data
    i=0
    for tr in template:
        # Perform check on channel and staiton names
        if tr.stats.station=='COSA' and tr.stats.channel=='S2':
            tr.stats.chanel='SE'
        if tr.stats.station=='COSA' and tr.stats.channel=='S1':
            tr.stats.channel='SN'
        if tr.stats.network=='AF':
            if not 'original_data' in locals():
                original_data=read(datasource+tr.stats.starttime.datetime.strftime('Y%Y/R%j.01')+\
                               '/'+tr.stats.station+'.'+tr.stats.network+'.*'+\
                               tr.stats.channel[-1]+'.'+\
                               tr.stats.starttime.datetime.strftime('%Y.%j'))
            else:
                original_data+=read(datasource+tr.stats.starttime.datetime.strftime('Y%Y/R%j.01')+\
                               '/'+tr.stats.station+'.'+tr.stats.network+'.*'+\
                               tr.stats.channel[-1]+'.'+\
                               tr.stats.starttime.datetime.strftime('%Y.%j'))
        else:
            if not 'original_data' in locals():
                original_data=read(GeoNet+tr.stats.starttime.datetime.strftime('%Y%m%d')+\
                               '/*'+tr.stats.station+'.*'+\
                               tr.stats.channel[-1]+'.SAC')
            else:
                original_data+=read(GeoNet+tr.stats.starttime.datetime.strftime('%Y%m%d')+\
                               '/*'+tr.stats.station+'.*'+\
                               tr.stats.channel[-1]+'.SAC')
        picks.append(PICK(station=original_data[i].stats.station,
                        channel=original_data[i].stats.channel[0]+original_data[i].stats.channel[2],
                        impulsivity='E', phase='S',
                        weight='3', polarity='',
                        time=tr.stats.starttime,
                        coda='', amplitude='', peri='',
                        azimuth='', velocity='', AIN='', SNR='',
                        azimuthres='', timeres='',
                        finalweight='', distance='',
                        CAZ=''))
        i+=1
    original_data.merge()
    print 'I have '+str(len(original_data))+' traces of data'
    print 'For which I have '+str(len(picks))+' picks'

    second_gen_template=template_gen._template_gen(picks, original_data,\
                                                           length2, 'all')
    third_gen_template=template_gen._template_gen(picks, original_data,\
                                                           length3, 'all')
    # Check that there actually is data for every channel
    missing_data=False
    for tr in second_gen_template:
        try:
            tr.split()
            if not 'temp' in locals():
                temp=Stream(tr)
            else:
                temp+=tr
        except:
            print 'No data for: '+tr.stats.station+' '+tr.stats.channel
            missing_data=True
    second_gen_template=temp
    del temp

    for tr in third_gen_template:
        try:
            tr.split()
            if not 'temp' in locals():
                temp=Stream(tr)
            else:
                temp+=tr
        except:
            print 'No data for: '+tr.stats.station+' '+tr.stats.channel
            missing_data=True
    third_gen_template=temp
    del temp

    if missing_data:
        for tr in template:
            for x in second_gen_template:
                if tr.stats.station==x.stats.station and tr.stats.channel==x.stats.channel:
                    if not 'temp' in locals():
                        temp=Stream(tr)
                    else:
                        temp+=tr
        template_out=temp
        del temp
        print 'Overwriting old template that had spurious data'
        # template_out.plot()
        template_out.write(tfile, format='mseed')

    # Write out the templates
    if not os.path.isdir(out2):
        os.makedirs(out2)
    if not os.path.isdir(out3):
        os.makedirs(out3)
    try:
        second_gen_template.write(out2+'/'+tfile.split('/')[-1], format='mseed')
    except NotImplementedError:
        second_gen_template=second_gen_template.split()
        second_gen_template.write(out2+'/'+tfile.split('/')[-1], format='mseed')
        f.write('Had to split: '+out2+'/'+tfile.split('/')[-1])
    print 'Written '+str(length2)+' second long template to: '+out2+'/'+tfile.split('/')[-1]
    try:
        second_gen_template.write(out2+'/'+tfile.split('/')[-1], format='mseed')
    except NotImplementedError:
        second_gen_template=second_gen_template.split()
        second_gen_template.write(out2+'/'+tfile.split('/')[-1], format='mseed')
        f.write('Had to split: '+out2+'/'+tfile.split('/')[-1])
    print 'Written '+str(length3)+' second long template to: '+out3+'/'+tfile.split('/')[-1]
f.close()

# Compute the stacks of the original templates
template_streams=[read(tfile) for tfile in templates]

groups=clustering_group_delays(template_streams)
ID=1
for group in groups:
    template_stack=stacking.PWS_stack(group, 2)
    template_stack.plot()
    template_stack.write('stack_templates/brightness_group_'+ID, format='mseed')
    ID+=1
