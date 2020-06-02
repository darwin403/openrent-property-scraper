import logging
from math import ceil, sqrt
import os
import re
from concurrent.futures import ThreadPoolExecutor as PoolExecutor
from functools import reduce

import coloredlogs
import requests
from utils import excel

coloredlogs.install(
    fmt='%(asctime)s [%(programname)s] %(levelname)s %(message)s')


# threads
CONCURRENCY = 1


# load postcodes
postcodes = []
with open('postcodes.txt') as f:
    for key, postcode in enumerate(f):
        if not postcode.strip():
            continue
        postcodes.append(postcode.strip())


# fetch all properties for given ids
def get_properties(ids):
    if not ids:
        return

    query_params = "&".join(['ids=%s' % i for i in ids])
    url = "https://www.openrent.co.uk/search/propertiesbyid?%s" % query_params

    try:
        r = requests.get(url)
        return r.json()
    except Exception as e:
        logging.error('Request failed: %s' % e)

    return []


# gather stats of shared properties with images
def get_stats(properties):
    rent_properties = [i for i in properties if i['letAgreed']
                       == False if i["imageUrl"] if "Shared" in i["title"]]
    let_properties = [i for i in properties if i['letAgreed']
                      == True if "Shared" in i["title"]]

    rent_count = len(rent_properties)
    let_count = len(let_properties)
    # not the same as len(properties)
    total_count = rent_count + let_count

    let_percentage = round((let_count/total_count)*100,
                           2) if let_count != 0 else 0
    let_total_price = reduce(
        lambda a, b: a + b['rentPerMonth'], let_properties, 0)
    let_average_price = round(
        let_total_price/let_count, 2) if let_count != 0 else 0

    return (rent_count, let_count, let_percentage, let_average_price)


# task to get properties for given postcode
def task_properties(postcode):
    url = 'https://www.openrent.co.uk/properties-to-rent/?term=%s&bedrooms_max=-1' % postcode

    try:
        r = requests.get(url)
    except Exception as e:
        logging.error('Request failed: %s' % e)
        return (False, (postcode,) + (0,)*4)

    ids_match = re.search(
        r"PROPERTYIDS = \[(.*?)\];", r.text, re.MULTILINE | re.DOTALL)

    if not ids_match:
        logging.warning('%s: No property ids founds on: %s' % (postcode, url))
        return (False, (postcode,) + (0,)*4)

    ids_raw = ids_match.group(1).split(',')
    ids = [i.strip() for i in ids_raw if i.strip()]

    properties = []

    chunk_size = 50
    chunks = [ids[i:i + chunk_size] for i in range(0, len(ids), chunk_size)]

    # multi threaded pagination
    with PoolExecutor(max_workers=ceil(sqrt(CONCURRENCY))) as executor:
        for properties_chunk in executor.map(get_properties, chunks):
            properties += properties_chunk

    stats = get_stats(properties)
    return (True, (postcode,) + stats)


if __name__ == "__main__":
    logging.info('bot started.')
    try:
        # multi thread over all postcodes
        with PoolExecutor(max_workers=ceil(sqrt(CONCURRENCY))) as executor:
            for (status, row) in executor.map(task_properties, postcodes):
                excel.insert(row[0], {
                    "totalRentCount": row[1],
                    "totalLetCount": row[2],
                    "totalLetPercentage": row[3],
                    "totalLetAverage": row[4]
                })
                logging.info('[%s]: %s!' %
                             (row[0], 'done' if status == True else 'failed'))

    except Exception as e:
        logging.error(e)
    finally:
        logging.info('saving to file')
        excel.save()

        logging.info('bot completed.')
        
        # stall program
        input("Press any key to continue ...")
