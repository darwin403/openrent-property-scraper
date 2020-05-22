import requests
import re
from functools import reduce
from concurrent.futures import ThreadPoolExecutor as PoolExecutor
import xlsxwriter

# threads
CONCURRENCY = 1

# load pins
pins = []
with open('pins.csv') as f:
    for key, pin in enumerate(f):
        if key == 0:
            continue
        if not pin.strip():
            continue
        pins.append(pin.strip())


# clean ids
def clean(ids):
    return [i.strip() for i in ids if i.strip()]


# array chunks
def chunks(l, n):
    return [l[i:i + n] for i in range(0, len(l), n)]


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
        print('Request failed:', e)

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
    let_total_price = round(
        reduce(lambda a, b: a + b['rentPerMonth'], let_properties, 0), 2)
    let_average_price = round(
        let_total_price/let_count, 2) if let_count != 0 else 0

    return (rent_count, let_count, let_percentage, let_average_price)


# create new output file
wb = xlsxwriter.Workbook('openrent.xlsx')
ws = wb.add_worksheet()
ws.write_row(0, 0, ('Post Code', 'Total Rent',
                    'Total Let', '% Let', 'Average Let Price'))


# task to get properties for given pin
def task_properties(pin):
    row = pins.index(pin) + 1
    url = 'https://www.openrent.co.uk/properties-to-rent/?term=%s&bedrooms_max=-1' % pin

    try:
        r = requests.get(url)
    except Exception as e:
        print('Request failed:', e)
        ws.write_row(row, 0, (pin, ) + (0,)*4)
        return (pin, False)

    ids_match = re.search(
        r"PROPERTYIDS = \[(.*?)\];", r.text, re.MULTILINE | re.DOTALL)

    if not ids_match:
        ws.write_row(row, 0, (pin, ) + (0,)*4)
        print('%s: No property ids founds on: %s' % (pin, url))
        return (pin, False)

    ids_raw = ids_match.group(1).split(',')
    ids = clean(ids_raw)

    properties = []

    # multi thread fetch
    with PoolExecutor(max_workers=20) as executor:
        for properties_chunk in executor.map(get_properties, chunks(ids, 50)):
            properties += properties_chunk

    stats = get_stats(properties)
    ws.write_row(row, 0, (pin, ) + stats)
    return (pin, True)


if __name__ == "__main__":
    try:
        # multi thread over all pins
        with PoolExecutor(max_workers=CONCURRENCY) as executor:
            for (pin, status) in executor.map(task_properties, pins):
                print('%s: %s!' % (pin, 'done' if status == True else 'failed'))

        wb.close()
    except Exception as e:
        # save existing data on any error
        wb.close()
        print(e)
