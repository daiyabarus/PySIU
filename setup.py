#!/usr/bin/env python
# coding=utf-8

__author__ = 'Esteban Garcia-Gurtubay'
__copyright__ = 'Ericsson Spain 2013'
__version__ = 'R13A01'
__email__ = 'esteban.garcia.gurtubay@gmail.com'
__date__ = '19/06/2013 17:07:15'


from distutils.core import setup

oss_install_dir = '/export/customer_adaptations/scmty'

setup(
    name='SCMTY',
    version = __version__,
    license='LICENSE.txt',
    author=__author__,
    author_email=__email__,
    description='SIU CM Tool Yoigo (SCMTY)',
    #packages=[''],
    #scripts=['],
    data_files=[(oss_install_dir, [
                                   'scmty/__init__.py',
                                   'scmty/scmty_get_siu_data.py',
                                   'scmty/scmty_format_data.py',
                                   'scmty/scmty_file_deleter.py',
                                   'scmty/scmty_siu_backup.py',
                                   'scmty/scmty_set_params.py',
                                   'scmty/scmty_delete_mos.py',
                                   'README.rst',
                                   'crontab_sample.txt',
                                    ]),

                (oss_install_dir + '/etc', [
                                   'scmty/etc/config.yaml',
                                    ]),

                (oss_install_dir + '/PySIU', [
                                   'scmty/PySIU/__init__.py',
                                   'scmty/PySIU/siu_wrapper.py',
                                   'scmty/PySIU/oss_siu_data.py',
                                    ]),

                ]
)
