#!/usr/bin/python
"""
Function to generate template waveforms and information to go with them for the\
application of cross-correlation of seismic data for the detection of repeating\
events.

Part of the EQcorrscan module to read nordic format s-files\
EQcorrscan is a python module designed to run match filter routines for\
seismology, within it are routines for integration to seisan and obspy.\
With obspy integration (which is necessary) all main waveform formats can be\
read in and output.

This main section contains a script, LFE_search.py which demonstrates the usage\
of the built in functions from template generation from picked waveforms\
through detection by match filter of continuous data to the generation of lag\
times to be used for relative locations.

The match-filter routine described here was used a previous Matlab code for the\
Chamberlain et al. 2014 G-cubed publication.  The basis for the lag-time\
generation section is outlined in Hardebeck & Shelly 2011, GRL.

Code generated by Calum John Chamberlain of Victoria University of Wellington,\
2015.


.. rubric:: Note
Pre-requisites:
    - gcc             - for the installation of the openCV correlation routine
    - python-cv2      - Python bindings for the openCV routines
    - python-joblib   - used for parallel processing
    - python-obspy    - used for lots of common seismological processing
                        - requires:
                            - numpy
                            - scipy
                            - matplotlib
    - NonLinLoc       - used outside of all codes for travel-time generation

Copyright 2015 Calum Chamberlain

This file is part of EQcorrscan.

    EQcorrscan is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    EQcorrscan is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with EQcorrscan.  If not, see <http://www.gnu.org/licenses/>.

"""

def from_sfile(sfile, lowcut, highcut, samp_rate, filt_order, length, swin,\
               debug=0):
    """
    Function to read in picks from sfile then generate the template from the
    picks within this and the wavefile found in the pick file.

    :type sfile: string
    :param sfile: sfilename must be the\
    path to a seisan nordic type s-file containing waveform and pick\
    information.
    :type lowcut: float
    :param lowcut: Low cut (Hz), if set to None will look in template\
            defaults file
    :type highcut: float
    :param lowcut: High cut (Hz), if set to None will look in template\
            defaults file
    :type samp_rate: float
    :param samp_rate: New sampling rate in Hz, if set to None will look in\
            template defaults file
    :type filt_order: int
    :param filt_order: Filter level, if set to None will look in\
            template defaults file
    :type swin: str
    :param swin: Either 'all', 'P' or 'S', to select which phases to output.
    :type length: float
    :param length: Extract length in seconds, if None will look in template\
            defaults file.
    :type debug: int
    :param debug: Debug level, higher number=more output.
    """
    # Perform some checks first
    import os
    import sys
    if not os.path.isfile(sfile):
        raise IOError('sfile does not exist')

    from eqcorrscan.utils import Sfile_util
    # Read in the header of the sfile
    wavefiles=Sfile_util.readwavename(sfile)
    pathparts=sfile.split('/')[0:len(sfile.split('/'))-1]
    wavpath=''
    for part in pathparts:
        if part == 'REA':
            part='WAV'
        wavpath+=part+'/'
    from obspy import read as obsread
    from eqcorrscan.utils import pre_processing
    # Read in waveform file
    for wavefile in wavefiles:
        print "I am going to read waveform data from: "+wavpath+wavefile
        if 'st' in locals():
            st+=obsread(wavpath+wavefile)
        else:
            st=obsread(wavpath+wavefile)
    for tr in st:
        if tr.stats.sampling_rate < samp_rate:
            print 'Sampling rate of data is lower than sampling rate asked for'
            print 'As this is not good practice for correlations I will not do this'
            raise ValueError("Trace: "+tr.stats.station+" sampling rate: "+\
                             str(tr.stats.sampling_rate))
    # Read in pick info
    picks=Sfile_util.readpicks(sfile)
    print "I have found the following picks"
    for pick in picks:
        print pick.station+' '+pick.channel+' '+pick.phase+' '+str(pick.time)

    # Process waveform data
    st=pre_processing.shortproc(st, lowcut, highcut, filt_order,\
                      samp_rate, debug)
    st1=_template_gen(picks, st, length, swin)
    return st1

def from_contbase(sfile, contbase_list, lowcut, highcut, samp_rate, filt_order,\
                 length, prepick, swin, debug=0):
    """
    Function to read in picks from sfile then generate the template from the
    picks within this and the wavefiles from the continous database of day-long
    files.  Included is a section to sanity check that the files are daylong and
    that they start at the start of the day.  You should ensure this is the case
    otherwise this may alter your data if your data are daylong but the headers
    are incorrectly set.

    :type sfile: string
    :param sfile: sfilename must be the path to a seisan nordic type s-file \
            containing waveform and pick information, all other arguments can \
            be numbers save for swin which must be either P, S or all \
            (case-sensitive).
    :type contbase_list: List of tuple of string
    :param contbase_list: List of tuples of the form ['path', 'type', 'network']\
                    Where path is the path to the continuous database, type is\
                    the directory structure, which can be either Yyyyy/Rjjj.01,\
                    which is the standard IRIS Year, julian day structure, or,\
                    yyyymmdd which is a single directory for every day.
    :type lowcut: float
    :param lowcut: Low cut (Hz), if set to None will look in template\
            defaults file
    :type highcut: float
    :param lowcut: High cut (Hz), if set to None will look in template\
            defaults file
    :type samp_rate: float
    :param samp_rate: New sampling rate in Hz, if set to None will look in\
            template defaults file
    :type filt_order: int
    :param filt_order: Filter level, if set to None will look in\
            template defaults file
    :type length: float
    :param length: Extract length in seconds, if None will look in template\
            defaults file.
    :type prepick: float
    :param prepick: Pre-pick time in seconds
    :type swin: str
    :param swin: Either 'all', 'P' or 'S', to select which phases to output.
    :type debug: int
    :param debug: Level of debugging output, higher=more
    """
    # Perform some checks first
    import os, sys
    if not os.path.isfile(sfile):
        raise IOError('sfile does not exist')

    # import some things
    from eqcorrscan.utils import Sfile_util
    from eqcorrscan.utils import pre_processing
    import glob
    from obspy import UTCDateTime

    # Read in the header of the sfile
    header=Sfile_util.readheader(sfile)
    day=UTCDateTime(str(header.time.year)+'-'+str(header.time.month).zfill(2)+\
                    '-'+str(header.time.day).zfill(2))

    # Read in pick info
    picks=Sfile_util.readpicks(sfile)
    print "I have found the following picks"
    pick_chans=[]
    used_picks=[]
    for pick in picks:
        if not pick.station+pick.channel in pick_chans and pick.phase in ['P','S']:
            pick_chans.append(pick.station+pick.channel)
            used_picks.append(pick)
            print pick
            for contbase in contbase_list:
                if contbase[1] == 'yyyy/mm/dd':
                    daydir=str(day.year)+'/'+str(day.month).zfill(2)+'/'+\
                            str(day.day).zfill(2)
                elif contbase[1]=='Yyyyy/Rjjj.01':
                    daydir='Y'+str(day.year)+'/R'+str(day.julday).zfill(3)+'.01'
                elif contbase[1]=='yyyymmdd':
                    daydir=str(day.year)+str(day.month).zfill(2)+str(day.day).zfill(2)
                if 'wavefiles' in locals():
                    wavefiles+=glob.glob(contbase[0]+'/'+daydir+'/*'+pick.station+\
                    '.*')
                else:
                    wavefiles=(glob.glob(contbase[0]+'/'+daydir+'/*'+pick.station+\
                    '.*'))
        elif pick.phase in ['P','S']:
            print 'Duplicate pick '+pick.station+' '+pick.channel+' '+pick.phase+\
            ' '+str(pick.time)
        elif pick.phase =='IAML':
            print 'Amplitude pick '+pick.station+' '+pick.channel+' '+pick.phase+\
            ' '+str(pick.time)
    picks=used_picks
    wavefiles=list(set(wavefiles))

    # Read in waveform file
    from obspy import read as obsread
    wavefiles.sort()
    for wavefile in wavefiles:
        print "I am going to read waveform data from: "+wavefile
        if 'st' in locals():
            st+=obsread(wavefile)
        else:
            st=obsread(wavefile)
    # Porcess waveform data
    st.merge(fill_value='interpolate')
    for tr in st:
        tr=pre_processing.dayproc(tr, lowcut, highcut, filt_order,\
                                samp_rate, debug, day)
    # Cut and extract the templates
    st1=_template_gen(picks, st, length, swin, prepick=prepick)
    return st1


def _template_gen(picks, st, length, swin, prepick=0.05, plot=False):
    """
    Function to generate a cut template in the obspy
    Stream class from a given set of picks and data, also in an obspy stream
    class.  Should be given pre-processed data (downsampled and filtered)

    :type picks: :class: 'makesfile.pick'
    :param picks: Picks to extract data around
    :type st: :class: 'obspy.Stream'
    :param st: Stream to etract templates from
    :type length: float
    :param length: Length of template in seconds
    :type swin: string
    :param swin: P, S or all
    :type prepick: float
    :param prepick: Length in seconds to extract before the pick time\
            default is 0.05 seconds
    :type plot: bool
    :param plot: To plot the template or not, default is True
    """
    from eqcorrscan.utils.Sfile_util import PICK
    from eqcorrscan.utils.EQcorrscan_plotting import pretty_template_plot as tplot
    from obspy import Stream
    import copy, warnings
    stations=[]
    channels=[]
    st_stachans=[]
    for pick in picks:
        stations.append(pick.station)
        channels.append(pick.channel)
    for tr in st:
        st_stachans.append(tr.stats.station+'.'+tr.stats.channel)
    for i in xrange(len(stations)):
        if not stations[i]+'.'+channels[i] in st_stachans:
            warnings.warn('No data provided for '+stations[i]+'.'+channels[i])
    # Select which channels we actually have picks for
    for tr in st:
        if tr.stats.station in stations:
            if swin=='all':
                if len(tr.stats.channel)==3:
                    temp_channel=tr.stats.channel[0]+tr.stats.channel[2]
                elif len(tr.stats.channel)==2:
                    temp_channel=tr.stats.channel
                # if temp_channel in channels:
                tr.stats.channel=temp_channel
                if 'st1' in locals():
                    st1+=tr
                else:
                    st1=Stream(tr)
            else:
                if 'st1' in locals():
                    st1+=tr
                else:
                    st1=Stream(tr)
    st=copy.deepcopy(st1)
    del st1
    if plot:
        stplot=st.copy()
    from obspy.core.trace import Trace
    # Cut the data
    for tr in st:
        if 'starttime' in locals():
            del starttime
        if swin=='all':
            for pick in picks:
                if pick.station==tr.stats.station and \
                    pick.channel==tr.stats.channel and\
                    pick.phase=='P':
                    starttime=pick.time-prepick
                elif pick.station==tr.stats.station and\
                    tr.stats.channel[-1] in ['1','2','N','E'] and\
                    pick.phase=='S':
                    starttime=pick.time-prepick
        else:
            for pick in picks:
                if pick.station==tr.stats.station and pick.phase==swin:
                    starttime=pick.time-prepick
        if 'starttime' in locals():
            print "Cutting "+tr.stats.station+'.'+tr.stats.channel
            tr.trim(starttime=starttime,endtime=starttime+length, nearest_sample=False)
            print tr.stats.starttime
            print tr.stats.endtime
            if 'st1' in locals():
                st1+=tr
            else:
                st1=Stream(tr)
        else:
            print 'No pick for '+tr.stats.station+'.'+tr.stats.channel
        # Ensure that the template is the correct length
        if len(tr.data) == (tr.stats.sampling_rate*length)+1:
            tr.data=tr.data[0:-1]
    if plot:
        tplot(st1, background=stplot.trim(st1.sort(['starttime'])[0].stats.starttime-10,\
                                        st1.sort(['starttime'])[-1].stats.endtime+10))
        del stplot
    del st
    # st1.plot(size=(800,600))
    return st1


if __name__=='__main__':
    import sys, os
    if len(sys.argv) != 2:
        print 'Requires 1 arguments: sfilename'
        sys.exit()
    else:
        sfile=str(sys.argv[1])
        template=from_sfile(sfile)
        from obspy import read
        template.write(sfile+'_template.ms', format="MSEED")
