# emblem-exporter

GIO wrapper script written in Python 3, designed for rapid import/export and clearing of Nautilus/Caja emblems. It will use the GIO cli to generate a JSON export of all the emblems attached to files/folders in a specified path. Similarly, it can ingest a JSON file to reapply all possible emblems to items in a certain path.

### How to use

Run the following command and it will explain itself:

```
python3 emblem-exporter.py -h
```

### But I need some examples, dammit!

Alright, alright. Let's say you want export all the emblems in your home folder and subfolders. You can use:

```
python3 emblem-exporter.py -e -r /home/username emblems.json
```

to recursively scan **/home/username** and save any detected emblems into **emblems.json**.

Later on, once you've messed about with your emblems and irreparably mucked things up, you can import the saved state from the **emblems.json** file, by using:

```
python3 emblem-exporter.py -i emblems.json
```

Aren't you glad you took a backup, eh?

### What if I want to nuke all my emblems and clear out a path?

You can use the following command to recursively clear out a path:

```
python3 emblem-exporter.py -c -r /path_to_clear
```

BUT BE CAREFUL AS THE CHANGES ARE PERMANENT and there's no way to recover your emblems at a later point. Unless you have a neatly exported JSON file, of course.

### Can I use this script to migrate my emblems to a different host?

Yes, as long as the absolute paths on that host are the same (for the JSON items with exported emblems), you'll be able to migrate everything correctly. Currently there's no support for relative paths, but it may be added in the future.

