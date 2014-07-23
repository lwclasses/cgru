#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import shutil
import signal
import re
import json

import af

from optparse import OptionParser

Parser = OptionParser(
    usage="%prog [options]\n\tType \"%prog -h\" for help",
    version="%prog 1.0"
)

Parser.add_option('-s', '--sources',  dest='sources',  type  ='string',     default='',    help='Sources')
Parser.add_option('-d', '--dest',     dest='dest',     type  ='string',     default='',    help='Destination')
Parser.add_option('-r', '--refs',     dest='refs',     type  ='string',     default='',    help='References')
Parser.add_option('-t', '--template', dest='template', type  ='string',     default='',    help='Shot template')
Parser.add_option('-p', '--padding',  dest='padding',  type  ='string',     default='',    help='Shot renaming padding')
Parser.add_option('-u', '--uppercase',dest='uppercase',action='store_true', default='',    help='Rename shot uppercase')
Parser.add_option('-m', '--move',     dest='move',     action='store_true', default=False, help='Move source files, not copy')
Parser.add_option('-A', '--afanasy',  dest='afanasy',  action='store_true', default=False, help='Use Afanasy to copy sources')
Parser.add_option(      '--afuser',   dest='afuser',   type  ='string',     default='',    help='Afanasy user')
Parser.add_option(      '--afcap',    dest='afcap',    type  ='int',        default=100,   help='Afanasy capacity')
Parser.add_option(      '--afmax',    dest='afmax',    type  ='int',        default=5,     help='Afanasy max running tasks')
Parser.add_option('--shot_src',       dest='shot_src', type  ='string',     default='SRC', help='Shot sources folder')
Parser.add_option('--shot_ref',       dest='shot_ref', type  ='string',     default='REF', help='Shot references folder')
Parser.add_option('--test',           dest='test',     action='store_true', default=False, help='Test inputs only')

Out = []


def errExit(i_msg):
    Out.append({'error': i_msg})
    Out.append({'status': 'error'})
    print(json.dumps({'deploy': Out}, indent=4))
    sys.exit(1)


def interrupt(signum, frame):
    errExit('Interrupt received')


signal.signal(signal.SIGTERM, interrupt)
signal.signal(signal.SIGABRT, interrupt)
signal.signal(signal.SIGINT, interrupt)

SameShotSeparators = '._-'


def isSameShot(i_shot, i_name):
    i_shot = i_shot.lower()
    i_name = i_name.lower()
    for s in SameShotSeparators:
        if i_name.find(i_shot + s) == 0:
            return True
    return False


(Options, args) = Parser.parse_args()

if Options.sources == '':
    errExit('Sources are not specified')

if not os.path.isdir(Options.sources):
    errExit('Sources folder does not exist')

if Options.template == '':
    errExit('Shot template is not specified')

if not os.path.isdir(Options.template):
    errExit('Shot template folder does not exist')

if not Options.test:
    if Options.dest == '':
        errExit('Destination is not specified')

    if not os.path.isdir(Options.dest):
        errExit('Destination folder does not exist')

References = []
if Options.refs != '' and os.path.isdir(Options.refs):
    References = os.listdir(Options.refs)
# References.sort()

Sources = os.listdir(Options.sources)
Sources.sort()
Sources_skip = []
FIN_SRC = []
FIN_DST = []
for shot in Sources:
    if shot in Sources_skip:
        continue
    src = os.path.join(Options.sources, shot)
    if not os.path.isdir(src):
        Out.append({'warning': "\"%s\" is not a folder" % shot})
        continue

    src_sources = [src]

    for folder in Sources:
        if folder == shot:
            continue
        if isSameShot(shot, folder):
            Sources_skip.append(folder)
            src_sources.append(os.path.join(Options.sources, folder))

    src_refs = []
    for ref in References:
        if isSameShot(shot, ref):
            src_refs.append(os.path.join(Options.refs, ref))

    shot_name = shot

    # Rename shot padding:
    if Options.padding != '':
        words = re.findall(r'\D+', shot)
        digits = re.findall(r'\d+', shot)
        if len(words) == len(digits):
            shot_name = ''
            num = 0
            for word in words:
                padding = '1'
                if num < len(Options.padding):
                    padding = Options.padding[num]
                shot_name += word
                shot_name += ('%0' + padding + 'd') % int(digits[num])
                num += 1
                # print('"%s"->"%s"' % (shot, shot_name))

    # Rename shot uppercase:
    if Options.uppercase:
        shot_name = shot_name.upper()

    shot_dest = os.path.join(Options.dest, shot_name)

    Out_Shot = dict()
    Out_Shot['name'] = shot_name
    Out_Shot['src'] = []
    for src in src_sources:
        Out_Shot['src'].append(src)

    if len(src_refs):
        Out_Shot['ref'] = []
        for ref in src_refs:
            Out_Shot['ref'].append(ref)

    Out.append({'shot': Out_Shot})

    if not Options.test:
        if not os.path.isdir(shot_dest):
            shutil.copytree(Options.template, shot_dest)

    for scr in src_sources:
        FIN_SRC.append(src)
        FIN_DST.append(os.path.join(shot_dest, Options.shot_src))
    for ref in src_refs:
        FIN_SRC.append(ref)
        FIN_DST.append(os.path.join(shot_dest, Options.shot_ref))

if Options.afanasy:
    job = af.Job('PUT ' + Options.dest)
    job.setUserName(Options.afuser)
    job.setMaxRunningTasks(Options.afmax)
    job.setMaxRunTasksPerHost(1)

    block = af.Block('put')
    block.setCapacity(Options.afcap)

    job.blocks.append(block)

Put = os.environ['CGRU_LOCATION'] + '/utilities/put.py'
Put = 'python "%s"' % os.path.normpath(Put)

for i in range(0, len(FIN_SRC)):
    src = FIN_SRC[i]
    dst = FIN_DST[i]

    if Options.move:
        if not Options.test:
            shutil.move(src, dst)
        continue

    cmd = Put
    cmd += ' -s "%s"' % src
    cmd += ' -d "%s"' % dst
    cmd += ' -n "%s"' % os.path.basename(src)

    if Options.test:
        continue

    if Options.afanasy:
        task = af.Task(os.path.basename(src))
        task.setCommand(cmd)
        block.tasks.append(task)
    else:
        os.system(cmd)

if Options.afanasy and not Options.test:
    job.send()

print(json.dumps({'deploy': Out}, indent=4))

