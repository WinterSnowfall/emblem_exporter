#!/usr/bin/env python3
'''
@author: Winter Snowfall
@version: 0.30
@date: 18/04/2023

Warning: Built for use with python 3.6+
'''

import json
import logging
import argparse
import subprocess
import os

##logging configuration block
logger_format = '%(asctime)s %(levelname)s >>> %(message)s'
#logging level for other modules
logging.basicConfig(format=logger_format, level=logging.ERROR) #DEBUG, INFO, WARNING, ERROR, CRITICAL
logger = logging.getLogger(__name__)
#logging level for current logger
logger.setLevel(logging.INFO) #DEBUG, INFO, WARNING, ERROR, CRITICAL

def path_crawler(base_path, recurse):
    items_to_process = []
    
    for dirpath, dirnames, filenames in os.walk(base_path):
        logger.debug(f'PC >>> Processing: {dirpath}')
            
        for dirname in dirnames:
            items_to_process.append(os.path.join(dirpath, dirname))
        for file in filenames:
            items_to_process.append(os.path.join(dirpath, file))
            
        if not recurse:
            break
            
    return items_to_process

def scan_emblems(scan_path, json_file, recurse, clear):    
    json_data_dict = {}
    
    logger.debug(f'Scan path: {scan_path}')
    logger.debug(f'Recurse: {recurse}')
    
    if recurse:
        logger.warning('Recursive scans can take a VERY long time.')
    
    items_to_process = path_crawler(scan_path, recurse)
    nr_items_to_process = len(items_to_process)
    
    logger.info(f'Number of items to scan for emblems: {nr_items_to_process}')
    
    processed_items = 0
    last_processed_percentage = 0
    processed_percentage = 0
    emblems_found = 0
    emblems_cleared = 0
    
    logger.info('Starting emblems scan...')
    
    try:
        for item in items_to_process:
            if recurse:
                processed_items += 1
            
            try:
                emblem_export_output = subprocess.run(['gio', 'info', '-a', 'metadata::emblems', item], 
                                                      stdout=subprocess.PIPE, text=True, check=True)
                emblem_metadata = emblem_export_output.stdout.splitlines()
                
                if len(emblem_metadata) == 5 and 'metadata::emblems' in emblem_metadata[4]:
                    try:
                        path = emblem_metadata[1].split(':')[1].strip()
                        emblems = [emblem.strip() for emblem in emblem_metadata[4].split(':')[3].strip()[1:-1].split(',')]
                        
                        # items with unset emblems will keep the attribute, but with a string, 
                        # not vstring, value of '[]' (this is either indended or an oversight) - 
                        # in this case, simply save an empty list in the JSON export file, 
                        # since this will enable clearing any existing emblem values on import
                        if len(emblems) == 1 and emblems[0] == "":
                            emblems = []
                        
                        if not clear:
                            logger.info(f'Found {emblems} emblem(s) for: {path}')
                            json_data_dict.update({path: emblems})
                            
                        else:
                            if len(emblems) > 0 :
                                emblems_found += 1
                        
                                try:
                                    # a string, not vstring, value of '[]' is set by Caja/Nautilus
                                    # on items that have previously had emblem(s) but all entries
                                    # have since been removed - replicate this "unset" behavior
                                    subprocess.run(['gio', 'set', path, 
                                                    'metadata::emblems', '[]'], check=True)
                                    emblems_cleared += 1
                                    
                                    logger.info(f'Found and cleared emblems for: {path}')
                                
                                except:
                                    raise
                            
                            else:
                                logger.debug(f'Found empty emblem for: {path}')
                            
                    except:
                        raise
            
            except KeyboardInterrupt:
                raise
            
            except:
                logger.warning(f'Failed to process: {item}')
                
            if recurse:
                processed_percentage =  processed_items * 100 // nr_items_to_process
                
                # update scan progress in 5% increments
                if processed_percentage % 5 == 0 and last_processed_percentage != processed_percentage:
                    last_processed_percentage = processed_percentage
                    # no point in showing 100%, as 0% is also rightfully ignored
                    if processed_percentage != 100:
                        logger.info(f'Proccessed {processed_items} items, {processed_percentage}% of total.')
    
    # allow the export of partially completed scans
    except KeyboardInterrupt:
        logger.Warning('Halting emblems scan due to KeyboardInterrupt!')
        
    logger.info('Emblems scan completed.')
        
    if clear:
        if emblems_found > 0:
            logger.info(f'Succesfully cleared {emblems_cleared}/{emblems_found} emblems.')
    
    else:
        if len(json_data_dict) > 0:
            json_export = json.dumps(json_data_dict, sort_keys=True, indent=4, separators=(',', ': '), ensure_ascii=False)
            
            logger.debug(f'JSON: {json_export}')
            
            with open(json_file, 'w') as file:
                file.write(json_export)
                
            logger.info('JSON export completed.')
                
        else:
            logger.warning('Nothing to export!')

def import_emblems(json_file):
    logger.info('Starting emblems import...')
    
    with open(json_file, 'r') as file:
        file_content = file.read()
        
    try:
        json_data = json.loads(file_content)
        items_to_process = len(json_data)
        
    except json.JSONDecodeError:
        logger.critical('Invalid JSON file structure!')
        raise SystemExit(4)
    
    if items_to_process > 0:
        logger.info(f'Number of emblems to apply: {items_to_process}')
        
        processed_items = 0
        
        for key in json_data:
            if os.path.isdir(key):
                logger.info(f'Applying {json_data[key]} emblem(s) to: {key}')
                
                try:
                    if len(json_data[key]) == 0:
                        # a string, not vstring, value of '[]' is set by Caja/Nautilus
                        # on items that have previously had emblem(s) but all entries
                        # have since been removed - replicate this "unset" behavior
                        subprocess.run(['gio', 'set', key, 
                                        'metadata::emblems', '[]'], check=True)
                    else:
                        subprocess.run(['gio', 'set', '-t', 'stringv', key, 
                                        'metadata::emblems', *json_data[key]], check=True)
                    
                    processed_items += 1
                    
                except:
                    logger.warning(f'Failed to import: {key}')
                
            else:
                logger.warning(f'Path not found: {key}')
             
        logger.info('Emblems import completed.')
                
        logger.info(f'Succesfully applied {processed_items}/{items_to_process} emblems.')
        
    else:
        logger.warning('Nothing to import!')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=('GIO wrapper for Caja/Nautilus emblems import/export and clearing'), 
                                     add_help=False)
    
    parser.add_argument('source')
    parser.add_argument('destination', nargs='?', default='')
    
    group = parser.add_mutually_exclusive_group(required=True)
    optional = parser.add_argument_group('optional arguments')
    
    group.add_argument('-i', '--import', help='Import emblem data from a JSON file', action='store_true')
    group.add_argument('-e', '--export', help='Export emblem data from a specified path to a JSON file', 
                       action='store_true')
    group.add_argument('-c', '--clear', help='Clear emblem data in a specified path', action='store_true')
    
    optional.add_argument('-h', '--help', action='help', help='show this help message and exit')
    optional.add_argument('-r', '--recursive', help='Recursively scan the path for emblems', 
                          action='store_true')
    
    args = parser.parse_args()
    
    if args.export:
        if os.path.isdir(args.source):
            if os.path.isdir(os.path.dirname(os.path.abspath(args.destination))):                
                scan_emblems(args.source, args.destination, args.recursive, False)
            else:
                logger.critical('Invalid export path!')
                raise SystemExit(2)
        else:
            logger.critical('Invalid source directory!')
            raise SystemExit(1)
    elif args.clear:
        if os.path.isdir(args.source):
            option = input("ALL EMBLEM DATA IN THE SPECIFIED PATH WILL BE LOST! PROCEED (Y/N)? ")
            
            if option.upper() == 'Y':
                scan_emblems(args.source, None, args.recursive, True)
            else:
                logger.info('Emblem clearing aborted.')
        else:
            logger.critical('Invalid clearing directory!')
            raise SystemExit(1)
    else:
        if os.path.isfile(args.source):
            import_emblems(args.source)
        else:
            logger.critical('Invalid source JSON file!')
            raise SystemExit(3)
