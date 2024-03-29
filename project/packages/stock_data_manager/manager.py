import sys
import os
import logging
import logging.handlers

from typing import List, Dict
from data_types import *

from .yf_positions_reader import *
from .yaml_file_reader import *
from .data_store import *
from .tiingo_api import *
from .iex_api import *
from .finnhub_api import *

LOGLEVEL = logging.DEBUG
LOGDIR = '{}/logs'.format(sys.path[0])

# Inputs
YF_PORTOFOLIO_DIR = '/Users/rakesh/Developer/portfolio_stats/inputs'
DEFAULT_PORTFOLIO_NAME = 'main'
PORTFOLIO_FILE_EXT = '.csv'
INDEX_TRACKERS_FILE = '/Users/rakesh/Developer/portfolio_stats/inputs/index_trackers.yml'
WATCHLIST_STOCKS_FILE = '/Users/rakesh/Developer/portfolio_stats/inputs/watchlist.yml'
STOCK_CATEGORIES_FILE = '/Users/rakesh/Developer/portfolio_stats/inputs/stock_categories.yml'
CATEGORY_ALLOCATION_FILE = '/Users/rakesh/Developer/portfolio_stats/inputs/category_allocation.yml'

# Outputs/Storage
STOCK_DATA_DIR = '/Users/rakesh/Developer/portfolio_stats/data'

# API Keys
TIINGO_API_KEY = '/Users/rakesh/Developer/portfolio_stats/api_keys/tiingo'
IEX_API_KEY = '/Users/rakesh/Developer/portfolio_stats/api_keys/iex'
FINNHUB_API_KEY = '/Users/rakesh/Developer/portfolio_stats/api_keys/finnhub'

class StockDataManager:

    _testing = False

    def __init__(self, console_logging_level=logging.INFO, portfolio_name=DEFAULT_PORTFOLIO_NAME):
        self._setup_logger(c_lvl=console_logging_level)
        self.portfolio_name = portfolio_name
        self.all_symbols = []
        self.stock_categories = {}
        self.category_allocations = {}
        self.index_tracker_stocks = []
        self.watchlist_stocks = []
        self.portfolio_stocks = []
        self.positions = []

    def _setup_logger(self, c_lvl: str):
        logger = logging.getLogger('StockDataManager')
        logger.setLevel(LOGLEVEL)
        if not os.path.exists(LOGDIR):
            os.mkdir(LOGDIR)
        rh = logging.handlers.RotatingFileHandler('{}/stock_data_manager.log'.format(LOGDIR), maxBytes=1000000, backupCount=3)
        rh.setLevel(LOGLEVEL)
        ch = logging.StreamHandler()
        ch.setLevel(c_lvl)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        rh.setFormatter(formatter)
        ch.setFormatter(formatter)
        logger.addHandler(rh)
        logger.addHandler(ch)
        logger.debug('Logger Intialized')
        self.logger = logger

    def _extract_symbols(self, positions: [Position]) -> List[str]:
        symbols = []
        for pos in positions:
            symbols.append(pos.symbol)
        return symbols

    def _remove_duplicats(self, symbols: List[str]) -> List[str]:
        d = {}
        for s in symbols:
            d[s] = 1
        return list(d)
    
    def _generate_stock(self, metadata: StockMetaData, latest: StockLatest, historical: StockHistorical) -> Stock:
        stock = Stock(symbol=metadata.symbol, company_name=metadata.company_name, industry=metadata.industry, issue_type=metadata.issue_type, latest_quote=latest.quote, day_quotes=historical.day_quotes)
        return stock

    def _check_category_allocations(self):
        total = 0
        for n in self.category_allocations.values():
            total += n
        if total != 100:
            self.logger.error('Category allocations do not add up to 100')
            raise ValueError('Category allocations do not add up to 100')

    def get_all_symbols(self) -> List[str]:
        return self.all_symbols

    def get_index_tracker_stocks(self) -> List[Stock]:
        return self.index_tracker_stocks

    def get_watchlist_stocks(self) -> List[Stock]:
        return self.watchlist_stocks

    def get_portfolio_stocks(self) -> List[Stock]:
        return self.portfolio_stocks
    
    def get_positions(self) -> List[Position]:
        return self.positions

    def get_stock_categories(self) -> Dict[str, str]:
        return self.stock_categories

    def get_category_allocations(self) -> Dict[str, float]:
        return self.category_allocations

    def fetch_stock_data(self, symbols: List[str]) -> List[Stock]:
        stock_data = []
        # Initialize data store
        ds = DataStore(data_dir=STOCK_DATA_DIR)
        # Instantiate API clients
        iex = IEXAPI(api_key_path=IEX_API_KEY)
        finnhub = FinnhubAPI(api_key_path=FINNHUB_API_KEY)
        tiingo = TiingoAPI(api_key_path=TIINGO_API_KEY)
        # Process all symbols
        for symbol in symbols:
            # Read data from local storage
            metadata = ds.read_stock_metadata(symbol=symbol)
            latest = ds.read_stock_latest(symbol=symbol)
            historical = ds.read_stock_historical(symbol=symbol)
            if not self._testing:
                # Fetch/update metadata for all symbols using IEX API
                metadata, updated = iex.update_metadata(symbol=symbol, metadata=metadata)
                # Update local storage
                if updated: ds.write_stock_metadata(symbol=symbol, metadata=metadata)
                # Fetch/update latest quote data for all symbols using Finhub API
                latest, updated = finnhub.update_latest(symbol=symbol, latest=latest)
                # Update local storage
                if updated: ds.write_stock_latest(symbol=symbol, latest=latest)
                # Fetch/update historical data for all symbols using Tiingo API
                historical, updated = tiingo.update_historical(symbol=symbol, historical=historical)
                # Update local storage
                if updated: ds.write_stock_historical(symbol=symbol, historical=historical)
            # Append stock data to final output
            stock_data.append(self._generate_stock(metadata=metadata, latest=latest, historical=historical))
            self.logger.info('Successfully refreshed data for {}'.format(symbol))
        return stock_data

    def refresh():
        self.run()

    def run(self):

        # Get positions data
        portfolio_file = YF_PORTOFOLIO_DIR + '/' + self.portfolio_name + PORTFOLIO_FILE_EXT
        self.logger.info('Portfolio File: {}'.format(portfolio_file))

        pos_reader = YFPositionsReader(file=portfolio_file)
        positions = pos_reader.run()

        # Get data from other stock files
        yfr = YamlFileReader()
        index_trackers = yfr.read_stocks_file(file=INDEX_TRACKERS_FILE)
        watchlist = yfr.read_stocks_file(file=WATCHLIST_STOCKS_FILE)
        self.stock_categories = yfr.read_category_file(file=STOCK_CATEGORIES_FILE)
        self.category_allocations = yfr.read_category_allocation_file(file=CATEGORY_ALLOCATION_FILE)
        self._check_category_allocations()

        self.positions = positions
        position_symbols = self._extract_symbols(positions=positions)

        # Create a list of all the symbols
        self.all_symbols = self._remove_duplicats(symbols=position_symbols+index_trackers+watchlist)

        # Update data
        stock_data = self.fetch_stock_data(symbols=self.all_symbols)

        # Create the various list of stocks
        for stock in stock_data:
            if stock.symbol in index_trackers:
                self.index_tracker_stocks.append(stock)
            if stock.symbol in watchlist:
                self.watchlist_stocks.append(stock)
            if stock.symbol in position_symbols:
                self.portfolio_stocks.append(stock)

        self.logger.info('Finished processing for {} symbols'.format(len(self.all_symbols)))
        
        return 0
