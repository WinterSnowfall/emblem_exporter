#!/usr/bin/env python3
'''
@author: Winter Snowfall
@version: 1.20
@date: 30/09/2023

Warning: Built for use with python 3.6+
'''

import json
import logging
import argparse
import subprocess
import signal
import os

# logging configuration block
LOGGER_FORMAT = '%(asctime)s %(levelname)s >>> %(message)s'
# logging level for other modules
logging.basicConfig(format=LOGGER_FORMAT, level=logging.ERROR)
logger = logging.getLogger(__name__)
# logging level for current logger
logger.setLevel(logging.INFO) # DEBUG, INFO, WARNING, ERROR, CRITICAL

# CONSTANTS
PATH_FIELD_INDICATOR = 'local path: '
PATH_FIELD_INDICATOR_LEN = len(PATH_FIELD_INDICATOR)
MIN_PROGRESS_INDICATOR_ITEMS = 10000
PROGRESS_INDICATOR_PERCENT_INTERVAL = 10
TYPE_FILTERS = ('file', 'folder')

def sigterm_handler(signum, frame):
    logger.debug('Stopping script due to SIGTERM.')

    raise SystemExit(0)

def sigint_handler(signum, frame):
    logger.debug('Stopping script due to SIGINT.')

    raise SystemExit(0)

def path_crawler(base_path, type_filter, recurse):
    items_to_process = []

    for dirpath, dirnames, filenames in os.walk(base_path):
        logger.debug(f'PC >>> Processing: {dirpath}')

        if not type_filter or type_filter == TYPE_FILTERS[0]:
            for file in filenames:
                items_to_process.append(os.path.join(dirpath, file))
        if not type_filter or type_filter == TYPE_FILTERS[1]:
            for dirname in dirnames:
                items_to_process.append(os.path.join(dirpath, dirname))

        if not recurse:
            break

    return items_to_process

def scan_metadata(scan_path, json_file, type_filter, recurse, setonly, metadata_filter, purge, clear):
    logger.debug(f'Scan path: {scan_path}')

    if metadata_filter == 'emblems':
        METADATA_TYPES = ['emblems']
        METADATA_FIELD_INDICATOR = 'metadata::emblems'
    else:
        METADATA_TYPES = metadata_filter.split(',')
        METADATA_FIELD_INDICATOR = 'metadata::'
        # with the exception of emblems, only basic string type metadata is supported
        logger.warning(f'Support for custom metadata fields is limited. Use with caution.')

    metadata_filter_nice = ', '.join(METADATA_TYPES)
    logger.info(f'Including the following metadata fields: {metadata_filter_nice}.')

    if recurse:
        logger.warning('Recursive scans can take a VERY long time.')

    items_to_process = path_crawler(scan_path, type_filter, recurse)
    nr_items_to_process = len(items_to_process)

    logger.info(f'Number of items to scan: {nr_items_to_process}')

    if nr_items_to_process > MIN_PROGRESS_INDICATOR_ITEMS:
        show_progress = True
    else:
        show_progress = False

    json_data = {}

    processed_items = 0
    last_processed_percentage = 0
    processed_percentage = 0
    items_exported = 0
    items_found = 0
    items_cleared = 0

    logger.info('Starting metadata scan...')

    try:
        for item in items_to_process:
            if show_progress:
                processed_items += 1

            try:
                metadata_export_output = subprocess.run(['gio', 'info', '-a', 'metadata::', item],
                                                      stdout=subprocess.PIPE, text=True, check=True)
                item_metadata = metadata_export_output.stdout.splitlines()

                metadata_dictionary = {}
                metadata_found = False
                no_clearing_failures = True
                item_path = None

                for metadata_line in item_metadata:
                    try:
                        # each item will have a local path value
                        item_path_index = metadata_line.find(PATH_FIELD_INDICATOR)
                        if item_path_index != -1:
                            item_path = metadata_line[item_path_index + PATH_FIELD_INDICATOR_LEN:]

                        # each item may have one more more metadata:: entries
                        metadata_tag_index = metadata_line.find(METADATA_FIELD_INDICATOR)

                        if metadata_tag_index != -1:
                            # theoretically impossible, but worth checking
                            if item_path is None:
                                raise Exception('Item has no associated local path')

                            metadata_field_name, metadata_value = metadata_line.split('::')[1].split(': ')

                            if metadata_field_name in METADATA_TYPES:
                                # export metadata
                                if not clear:
                                    if metadata_field_name == 'emblems':
                                        metadata_value = metadata_value[1:-1].split(', ')

                                        if len(metadata_value) == 1 and metadata_value[0] == '':
                                            # in this case, simply save an empty list in the JSON export file,
                                            # since it will enable clearing any existing emblem values on import
                                            metadata_value = []

                                    if (setonly and ((metadata_field_name != 'annotation' and metadata_value == '') or
                                                     (metadata_field_name == 'emblems' and len(metadata_value) == 0))):
                                        logger.info(f'Ignoring empty {metadata_field_name} for: {item_path}')
                                    else:
                                        # all items will have at last a blank annotation metadata entry
                                        if not (metadata_field_name == 'annotation' and metadata_value == ''):
                                            metadata_dictionary.update({metadata_field_name: metadata_value})
                                # clear or purge
                                else:
                                    try:
                                        if not purge:
                                            # a string, not vstring, value of '[]' is set by Caja/Nautilus
                                            # on items that have previously had emblem(s) but all entries
                                            # have since been removed - replicate this behavior
                                            if metadata_field_name == 'emblems':
                                                if metadata_value != '[]':
                                                    metadata_found = True
                                                    subprocess.run(['gio', 'set', item_path,
                                                                    'metadata::emblems', '[]'], check=True)
                                                    logger.info(f'Found and cleared emblems for: {item_path}')
                                            # for other fields simply set a blank value
                                            else:
                                                if metadata_value != '':
                                                    metadata_found = True
                                                    subprocess.run(['gio', 'set', item_path,
                                                                    f'metadata::{metadata_field_name}', ''], check=True)
                                                    logger.info(f'Found and cleared {metadata_field_name} for: {item_path}')

                                        else:
                                            # annotations will always be blank by default, so they cannot be purged
                                            if metadata_field_name == 'annotation':
                                                if metadata_value != '':
                                                    metadata_found = True
                                                    subprocess.run(['gio', 'set', item_path,
                                                                    'metadata::annotation', ''], check=True)
                                                    logger.info(f'Found and purged annotations for: {item_path}')

                                            # in order to purge metadata from an item and mark it as if
                                            # it never had metadata attached, one must remove the attribute
                                            # entirely - this is done by using the 'unset' value type
                                            else:
                                                metadata_found = True
                                                subprocess.run(['gio', 'set', '-t', 'unset', item_path,
                                                                f'metadata::{metadata_field_name}'], check=True)
                                                logger.info(f'Found and purged {metadata_field_name} for: {item_path}')
                                    
                                    except SystemExit:
                                        raise
            
                                    except:
                                        if not purge:
                                            logger.warning(f'Failed to clear {metadata_field_name} for: {item_path}')
                                        else:
                                            logger.warning(f'Failed to purge {metadata_field_name} for: {item_path}')

                                        no_clearing_failures = False

                            else:
                                logger.debug(f'Found excluded metadata field: {metadata_field_name}')

                    except:
                        raise

                if len(metadata_dictionary) > 0:
                    for key in metadata_dictionary.keys():
                        logger.info(f'Found {key}: {metadata_dictionary[key]} for {item_path}')
                    json_data.update({item_path: metadata_dictionary})
                    items_exported += 1

                if clear:
                    if metadata_found:
                        items_found += 1
                    if no_clearing_failures:
                        items_cleared += 1

            except SystemExit:
                raise

            except:
                logger.warning(f'Failed to process: {item}')

            if show_progress:
                processed_percentage = processed_items * 100 // nr_items_to_process

                # update scan progress in 5% increments
                if (processed_percentage % PROGRESS_INDICATOR_PERCENT_INTERVAL == 0 and
                    last_processed_percentage != processed_percentage):
                    last_processed_percentage = processed_percentage
                    # no point in showing 100%, as 0% is also rightfully ignored
                    if processed_percentage != 100:
                        logger.info(f'Proccessed {processed_items} items, {processed_percentage}% of total.')

    # allow the export of partially completed scans
    except SystemExit:
        logger.warning('Halting metadata scan due to termination signal!')

    logger.info('Metadata scan completed.')

    if clear:
        if items_found > 0:
            if purge:
                logger.info(f'Succesfully purged {items_cleared}/{items_found} items with metadata.')
            else:
                logger.info(f'Succesfully cleared {items_cleared}/{items_found} items with metadata.')

    else:
        if len(json_data) > 0:
            json_export = json.dumps(json_data, sort_keys=True, indent=4,
                                     separators=(',', ': '), ensure_ascii=False)

            logger.debug(f'JSON: {json_export}')

            with open(json_file, 'w') as file:
                file.write(json_export)

            logger.info('JSON export completed.')

            logger.info(f'Succesfully exported {items_exported} items with metadata.')

        else:
            logger.warning('Nothing to export!')

def import_metadata(json_file):
    logger.info('Starting metadata import...')

    with open(json_file, 'r') as file:
        file_content = file.read()

    try:
        json_data = json.loads(file_content)
        items_to_process = len(json_data)

    except json.JSONDecodeError:
        logger.critical('Invalid JSON file structure!')
        raise SystemExit(5)

    if items_to_process > 0:
        logger.info(f'Number of metadata entries to apply: {items_to_process}')

        processed_items = 0

        for item_path in json_data:
            no_import_failures = True

            if os.path.isfile(item_path) or os.path.isdir(item_path):
                metadata_dict = json_data[item_path]

                for metadata in metadata_dict:
                    try:
                        if metadata == 'emblems':
                            if len(metadata_dict[metadata]) == 0:
                                # a string, not vstring, value of '[]' is set by Caja/Nautilus
                                # on items that have previously had emblem(s) but all entries
                                # have since been removed - replicate this behavior
                                subprocess.run(['gio', 'set', item_path,
                                                'metadata::emblems', '[]'], check=True)
                            else:
                                subprocess.run(['gio', 'set', '-t', 'stringv', item_path,
                                                'metadata::emblems', *metadata_dict[metadata]], check=True)
                        else:
                            subprocess.run(['gio', 'set', item_path,
                                            f'metadata::{metadata}', metadata_dict[metadata]], check=True)

                        logger.info(f'Set {metadata} to {metadata_dict[metadata]} for {item_path}')

                    except:
                        no_import_failures = False
                        logger.warning(f'Failed to import: {metadata}')

                if no_import_failures:
                    processed_items += 1

            else:
                logger.warning(f'Path not found: {item_path}')

        logger.info('Metadata import completed.')

        logger.info(f'Succesfully applied metadata to {processed_items}/{items_to_process} items.')

    else:
        logger.warning('Nothing to import!')

if __name__ == '__main__':
    # catch SIGTERM and exit gracefully
    signal.signal(signal.SIGTERM, sigterm_handler)
    # catch SIGINT and exit gracefully
    signal.signal(signal.SIGINT, sigint_handler)

    parser = argparse.ArgumentParser(description=('GIO wrapper for Caja/Nautilus metadata import/export and clearing'),
                                     add_help=False)

    parser.add_argument('source')
    parser.add_argument('destination', nargs='?', default=None)

    group = parser.add_mutually_exclusive_group(required=True)
    optional = parser.add_argument_group('optional arguments')

    group.add_argument('-i', '--import', help='Import metadata from a JSON file', action='store_true')
    group.add_argument('-e', '--export', help='Export metadata from a specified path to a JSON file',
                       action='store_true')
    group.add_argument('-c', '--clear', help='Clear metadata in a specified path', action='store_true')

    optional.add_argument('-h', '--help', action='help', help='show this help message and exit')
    optional.add_argument('-m', '--metadata', help='Custom metadata field filter, e.g. "emblems,custom-icon"',
                          default='emblems')
    optional.add_argument('-r', '--recursive', help='Recursively scan the path for metadata',
                          action='store_true')
    optional.add_argument('-s', '--setonly', help='Ignore previously unset/cleared metadata during exports',
                          action='store_true')
    # removing the meta-attribute (or purging) is also useful for testing or restoring a path
    # to its original "pristine" state, before any metadata was ever applied with Caja/Nautilus
    optional.add_argument('-p', '--purge', help='Remove metadata along with its meta-attribute',
                          action='store_true')
    optional.add_argument('-t', '--type', help='Type filter that can be set to either "file" or "folder"',
                          default=None)

    args = parser.parse_args()

    # ignore unsupported values by clearing the filter
    if args.type and args.type not in TYPE_FILTERS:
        logger.warning(f'Ignoring unsupported type filter value of "{args.type}".')
        args.type = None

    if args.export:
        if os.path.isdir(args.source):
            if os.path.isdir(os.path.dirname(os.path.abspath(args.destination))):
                scan_metadata(args.source, args.destination, args.type,
                              args.recursive, args.setonly, args.metadata, None, False)
            else:
                logger.critical('Invalid export path!')
                raise SystemExit(2)
        else:
            logger.critical('Invalid source directory!')
            raise SystemExit(1)

    elif args.clear:
        if os.path.isdir(args.source):
            if args.purge:
                option = input('ALL METADATA IN THE SPECIFIED PATH WILL BE PURGED! PROCEED (Y/N)? ')
            else:
                option = input('ALL METADATA IN THE SPECIFIED PATH WILL BE LOST! PROCEED (Y/N)? ')

            if option.upper() == 'Y':
                scan_metadata(args.source, None, args.type, args.recursive,
                              None, args.metadata, args.purge, True)
            else:
                logger.info('Metadata clearing aborted.')
        else:
            logger.critical('Invalid clearing directory!')
            raise SystemExit(3)

    else:
        if os.path.isfile(args.source):
            import_metadata(args.source)
        else:
            logger.critical('Invalid source JSON file!')
            raise SystemExit(4)
