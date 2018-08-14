"""
"""

import os
# import sys
import warnings
import shutil
import re
import glob
# from collections import OrderedDict

# import astrocats
from astrocats import PATHS as AC_PATHS
# from astrocats.structures import struct

import pyastroschema as pas  # noqa
import pyastroschema.utils


def setup(log):

    # Clear output directory
    pattern = os.path.join(AC_PATHS.SCHEMA_OUTPUT, "", "*.json")
    old_files = sorted(glob.glob(pattern))
    old_files = [os.path.join(AC_PATHS.SCHEMA_OUTPUT, fname) for fname in old_files]
    log.info("Deleting {} old schema files.".format(len(old_files)))
    for fname in old_files:
        os.remove(fname)

    # Copy all `astroschema` schema files to the 'input' directory
    log.info("Copying `astroschema` schema files to input")
    astroschema_fnames = pas.copy_schema_files(AC_PATHS.SCHEMA_INPUT_ASTROSCHEMA, verbose=False)
    for fname in astroschema_fnames:
        base = os.path.basename(fname)
        log.debug("Copied '{}' to '{}'".format(base, fname))

    log.info("Copied {} files".format(len(astroschema_fnames)))

    # Load names of astrocats files (already in 'input')
    log.info("Loading `astrocats` schema file names from input")
    pattern = os.path.join(AC_PATHS.SCHEMA_INPUT_ASTROCATS, "*.json")
    astrocats_fnames = list(sorted(glob.glob(pattern)))
    # Add directory path
    pattern_path = os.path.dirname(pattern)
    astrocats_fnames = [os.path.join(pattern_path, fname) for fname in astrocats_fnames]

    log.info("Loaded {} file names".format(len(astrocats_fnames)))

    def get_output_fname(src, group):
        base = os.path.basename(src)
        if not base.lower().startswith(group.lower()):
            base = group.lower() + "_" + base
        dst = os.path.join(AC_PATHS.SCHEMA_OUTPUT, base)
        return dst

    # Store all source filenames from input and construct the destination names for output
    src_list = []
    dst_list = []
    astroschema_list = []
    fnames = [astroschema_fnames, astrocats_fnames]
    groups = ["astroschema", "astrocats"]
    log.info("Copying `astrocats` schema files to input")
    for src_files, grp in zip(fnames, groups):
        for src in src_files:
            src_list.append(src)
            dst = get_output_fname(src, grp)
            # Make sure there are no duplicates
            if dst in dst_list:
                idx = dst_list.index(dst)
                err = "Destination '{}' already exists for '{}', cannot be used for '{}'!".format(
                    dst, src_list[idx], src)
                log.raise_error(err, ValueError)

            dst_list.append(dst)
            if grp == 'astroschema':
                astroschema_list.append([src, dst])

    # Copy all input schema files to output with modified names
    log.info("Copying {} schema files to output".format(len(src_list)))
    for src, dst in zip(src_list, dst_list):
        shutil.copy(src, dst)
        base = os.path.basename(dst)
        log.debug("Copied '{}' : '{}' ==> '{}'".format(base, src, dst))
        check_schema_id(dst, log)

    warnings.warn(__file__ + ":setup() - Add a schema validation here!")

    # Modify astroschema files to use (e.g.) "astroschema_source.json" instead of "source.json"
    # This is also applied to 'id' attributes which is required for correct reference resolution
    log.info("Replacing astroschema internal references")
    rename_internal_astroschema_refs(astroschema_list)

    for dst in dst_list:
        base = os.path.basename(dst)
        # This is not needed when using `check_id` above...
        # set_schema_value(dst, "id", base)
        log.debug("Set `id` to '{}' in '{}'".format(base, dst))

    return


def check_schema_id(fname, log):
    """Make sure schema has `id` attribute matching filename.  Required for reference resolution.
    """
    data, *args = pas.utils.load_schema_dict(fname)
    base = os.path.basename(fname)
    if "id" not in data:
        err = "`id` is missing, but required in all schema (must match filename)!"
        log.raise_error(err, ValueError)
    elif data['id'] != base:
        err = "`id` '{}' must match filename '{}'!".format(data['id'], fname)
        log.raise_error(err, ValueError)

    return


'''
# This is no longer needed as `check_schema_id` is being used
def set_schema_value(fname, key, value, if_missing=False):
    data, *args = pas.utils.load_schema_dict(fname)
    if (key not in data) or (not if_missing):
        data[key] = value
    pas.utils.json_dump_file(data, fname)
    return
'''


def rename_internal_astroschema_refs(astroschema_list):
    """Rename internal schema references from old to new filenames.

    This is applied to both the 'id' and 'title' values and properties.

    """
    names = [os.path.basename(fname) for fname, _ in astroschema_list]
    mapping = [[nam, "astroschema_" + nam] for nam in names]
    # print(mapping)

    for _, fname in astroschema_list:
        if not os.path.exists(fname):
            raise RuntimeError("Schema file '{}' does not exist!".format(fname))

        with open(fname, 'r') as inn:
            schema = inn.read()

        for old, new in mapping:
            # schema = schema.replace(old, new)
            # Use `re` to avoid substrings e.g. 'foo_source.json' ==> 'foo_foo_source.json'
            schema = re.sub(r"\b{}\b".format(old), new, schema)

        with open(fname, 'w') as out:
            out.write(schema)

    return


'''
def output_schema(path_out, struct_obj, verbose=True):
    # Order of dictionary keys in output file
    sort_order = ['$schema', 'id', 'title', 'description', 'version',
                  'type', 'definitions', 'properties', 'required']

    def sort_item_func(item):
        """Method to generate key for sorting each item of a dictionary
        """
        kk = item[0]

        # Find the index of this key in the `sort_order` list
        idx = None
        for ii, sval in enumerate(sort_order):
            # Ignore text-case
            if kk.lower().startswith(sval.lower()):
                idx = ii
                break

        # Sort things first if found in `sort_order`
        if idx is not None:
            rv = "a_" + str(idx)
        # Then just sort alphabetically by the key
        else:
            rv = "b_" + str(kk)

        return rv

    def sort_dict_func(odict):
        """Method to sort an entire dictionary
        """
        out = OrderedDict(sorted(odict.items(), key=sort_item_func))
        return out

    if hasattr(struct_obj, "_SCHEMA"):
        schema = struct_obj._SCHEMA
    elif isinstance(struct_obj, str):
        if not os.path.exists(struct_obj):
            struct_obj = os.path.join(PATH_SCHEMA_INPUT, struct_obj)
        schema = pas.schema.SchemaDict(struct_obj)
    else:
        err = "Unexptected type '{}' for `struct_obj` '{}'".format(
            type(struct_obj), struct_obj)
        raise RuntimeError(err)

    # schema = struct_obj._SCHEMA
    _title = schema['title'].lower()
    fname = os.path.join(path_out, _title + ".json")
    schema.dump(fname, sort_func=sort_dict_func)
    # if verbose:
    #     print("saved structure '{}' schema to '{}'".format(_title, fname))
    return fname
'''