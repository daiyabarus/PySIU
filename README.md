
PySIU
=====

Description
-----------
PySIU is a custom Python library to interact with Ericsson SIU nodes, normally from an OSS-RC server.
It encapsulates the SSH sessions, allowing to automate SIU commands by script on a massive scale.
A JSON file is generated to record all the interaction with the SIU nodes.


Possible uses
-------------
* Massively change parameters in the SIUs in a matter of minutes
* Massive SIU Backup/Restore
* SIU configuration inventories


Sample
------
An example usage can be found in the test directory.
The example launches multiple SSH sessions in parallel towards the whole SIU network and execute an arbitrary number of commands.

