# simtools.py: routines for loading and pre-processing tick data

import datetime
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import time

# Reference
# https://wrds-www.wharton.upenn.edu/documents/774/Daily_TAQ_Client_Spec_v2.2a.pdf

# helper routing to log a message with time
def log_message( label_string ):
    ts = time.time()
    st = datetime.datetime.fromtimestamp( ts ).strftime( '%Y-%m-%d %H:%M:%S:%f' )
    print("{}: {}".format(st, label_string))

# load and normalize trade file
def loadtradefile(tickfilename):
    log_message( 'load trades' )
    trades = pd.read_csv(tickfilename, infer_datetime_format=True)
    log_message( 'load complete' )
    log_message( 'indexing trades' )
    format = '%Y%m%d%H:%M:%S.%f'

    # fix padding on time
    times = trades['TIME_M'].apply(lambda x: x.zfill(18))
    timestamps = trades['DATE'].astype(str) + times
    times = pd.to_datetime( timestamps, format = format )
    trades.index = times
    trades = trades.drop(columns=['DATE', 'TIME_M'])
    log_message( "index trades done" )
    
    # standardize column names
    trades.columns = ['symbol', 'suffix', 'trade_size', 'trade_px']
    
    # return a dataframe
    return trades

# load and normalize file
def loadquotefile(tickfilename):   
    log_message( 'load quotes' )
    quotes = pd.read_csv(tickfilename, infer_datetime_format=True)
    log_message( 'load complete' )
    log_message( 'indexing quotes' )
    format = '%Y%m%d%H:%M:%S.%f'

    # fix padding on time
    times = quotes['TIME_M'].apply(lambda x: x.zfill(18))
    timestamps = quotes['DATE'].astype(str) + times
    times = pd.to_datetime( timestamps, format = format )
    quotes.index = times
    quotes = quotes.drop(columns=['DATE', 'TIME_M'])
    log_message( "index quotes done" )
    
    # standardize column names
    quotes.columns = ['exch', 'bid_px', 'bid_size', 'ask_px', 'ask_size', 'qu_cond', 'qu_seqnum', 'natbbo_ind', 
                      'qu_cancel', 'qu_source', 'symbol', 'suffix']
    
    # return a dataframe
    return quotes

# make a merged file for simulation
# NOTE this currently doesn't support tickers with suffixes...
def makeTAQfile(trades, quotes):
    log_message( 'start merge' )
    taq = quotes.merge( trades, how = 'outer', on = 'symbol', left_index = True, right_index = True )
    log_message( 'end merge' )
    return taq
    
# TODO: calculate some stats on tick data
def datastats(somedataframe):
    return 1

# TODO: calculate some basic P&L
def profitandloss(somedataframe):
    return 1