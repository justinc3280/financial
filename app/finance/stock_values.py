from flask import flash
import requests
import json

key = 'S2IEL3KQTDWBOU86'

def get_current_price(symbol):
	function = 'GLOBAL_QUOTE'
	url = 'https://www.alphavantage.co/query?function={}&symbol={}&apikey={}'.format(function, symbol, key)
	try:
		data = json.loads(requests.get(url).text)
		quote = data.get('Global Quote')
		previous_close_price = float(quote.get('08. previous close'))
		current_price = float(quote.get('05. price'))
	except:
		flash('Could not load prices')
		return None
	return current_price  

def get_closing_value_on_date(symbol, date):
	return symbol