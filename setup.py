#!/usr/bin/env python
# coding=utf-8

__author__ = 'Esteban Garcia-Gurtubay'
__version__ = 'R13A01'
__date__ = '19/06/2013 17:07:15'


from distutils.core import setup # To make a pip .tar.gz package

setup(
    name='PySIU',
    version = __version__,
    license='LICENSE.txt',
    author=__author__,
    description='Python utility libraries for the Ericsson SIU nodes',
    packages=['pysiu'],
)
