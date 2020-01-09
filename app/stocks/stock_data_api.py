from datetime import datetime
import logging
import os
import requests

logger = logging.getLogger(__name__)


class StockDataApi:
    def __init__(self):
        self._alpha_vantage_api = AlphaVantageApi(
            os.environ.get('ALPHA_VANTAGE_API_KEY')
        )
        self._world_trading_data_api = WorldTradingDataApi(
            os.environ.get('WORLD_TRADING_DATA_API_KEY')
        )
        self._iex_cloud_api = IEXCloudApi(os.environ.get('IEX_CLOUD_API_KEY'))

    def get_historical_monthly_prices(self, symbol, start_date, end_date):
        if symbol in ['PSX', 'SBUX', 'VFINX']:
            # found issues with world trade data:
            # 1) SFTBY prices ended at 1/18/2019, now it works?
            # 2) SBUX and PSX missing data for 3/29/2019
            # 3) VFINX off by 1 cent on 2/28/2018 (251.28 should be 251.27)
            api = self._alpha_vantage_api
        else:
            api = self._world_trading_data_api
        monthly_prices = api.get_historical_monthly_prices(symbol, start_date, end_date)
        return monthly_prices

    def get_latest_price(self, symbol):
        return self._iex_cloud_api.get_latest_price(symbol)


# Abstract class
class BaseStockDataApi:
    def __init__(self, key):
        self._key = key

    def get_historical_monthly_prices(self, symbol, start_date, end_date):
        raise NotImplementedError

    def get_latest_price(self, symbol):
        raise NotImplementedError


class AlphaVantageApi(BaseStockDataApi):
    BASE_URL = 'https://www.alphavantage.co'

    def _get_time_series_monthly_data(self, symbol):
        url = f'{self.BASE_URL}/query?function=TIME_SERIES_MONTHLY_ADJUSTED&symbol={symbol}&apikey={self._key}'
        data = requests.get(url).json()
        historical_prices = data.get('Monthly Adjusted Time Series')
        if historical_prices is None:
            error_message = data.get('Note')
            logger.error(
                'No data from Alpha Vantage for symbol: %s. Error Message: %s',
                symbol,
                error_message,
            )
            return None
            # raise exception ?
        else:
            return historical_prices

    def get_historical_monthly_prices(self, symbol, start_date, end_date):
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')

        historical_prices = self._get_time_series_monthly_data(symbol)  # try catch?
        if historical_prices is None:
            return None

        monthly_closing_prices = {}
        for date_str, prices in historical_prices.items():
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            if start_date <= date_obj <= end_date:
                year_month_str = date_str[:7]
                if year_month_str not in monthly_closing_prices:
                    monthly_closing_prices[year_month_str] = float(
                        prices.get('4. close')
                    )
        return monthly_closing_prices


class WorldTradingDataApi(BaseStockDataApi):
    BASE_URL = 'https://www.worldtradingdata.com/api/v1'

    def get_historical_monthly_prices(self, symbol, start_date, end_date):
        url = f"""{self.BASE_URL}/history?symbol={symbol}&sort=newest&
                             date_from={start_date}&date_to={end_date}&api_token={self._key}"""
        data = requests.get(url).json()
        historical_prices = data.get('history')

        monthly_closing_prices = {}
        for date_str, prices in historical_prices.items():
            year_month_str = date_str[:7]
            if year_month_str not in monthly_closing_prices:
                monthly_closing_prices[year_month_str] = prices.get('close')
        return monthly_closing_prices


class IEXCloudApi(BaseStockDataApi):
    BASE_URL = 'https://cloud.iexapis.com/v1'

    def get_latest_price(self, symbol):
        url = self.BASE_URL + '/stock/{}/quote/?token={}'.format(symbol, self._key)
        quote = requests.get(url).json()
        return quote.get('latestPrice')


stock_data_api = StockDataApi()
