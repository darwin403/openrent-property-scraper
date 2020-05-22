import socket
import urllib3
import requests
from bs4 import BeautifulSoup


def get_proxies():
    response = requests.get("https://free-proxy-list.net/")
    soup = BeautifulSoup(response.text, 'lxml')
    table = soup.find('table', id='proxylisttable')
    list_tr = table.find_all('tr')
    list_td = [elem.find_all('td') for elem in list_tr]
    list_td = list(filter(None, list_td))
    list_ip = [elem[0].text for elem in list_td]
    list_ports = [elem[1].text for elem in list_td]
    list_proxies = [':'.join(elem) for elem in list(zip(list_ip, list_ports))]
    return list_proxies


proxies = get_proxies()

for proxy in proxies[:99]:
    print (proxy)