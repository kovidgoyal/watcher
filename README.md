watcher 
========

A daemon that exposes various system information efficiently over a socket.
Primarily useful for watching file system tress for changes, and using the
change notifications to efficiently display git branch names/dirty status, etc.

Also contains code to integrate with various applications that consume this
information, such as shells, vim, qtile, etc.
