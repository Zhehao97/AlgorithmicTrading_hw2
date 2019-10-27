import datetime
import numpy as np
import pandas as pd
import time
import sys

from simtools import log_message

# Lee-Ready tick strategy simulator

# Record a trade in our trade array
def record_trade( trade_df, idx, tick, stock_px, position, pnl, trade_px, trade_qty, trade_type='-', side='-' ):
    #print( "Trade! {} {} {} {}".format( idx, trade_px, trade_qty ) )
    trade_df.loc[ idx ] = [ tick, stock_px, position, pnl, trade_px, trade_qty, trade_type, side ]

    return

# TODO: calc P&L and other statistics
def trade_statistics( trade_df ):

    # TODO: calculate intraday P&L (time series). P&L has two components. Roughly:
    #       1. realized "round trip" P&L  sum of (sell price - buy price) * shares traded
    #       2. unrealized P&L of open position:  quantity held * (current price - avg price)
    adj_trade_df = adj_trades = trade_df[trade_df['trade_price'] != 0]
    intraday_pnl = adj_trade_df['current_pnl']

    # TODO: calculate maximum position (both long and short) and ending position
    max_long_position = adj_trade_df['current_position'].max()
    max_short_position = adj_trade_df['current_position'].min()
    ending_position = adj_trade_df['current_position'][-1]

    # TODO: calculate worst and best intraday P&L
    best_pnl = intraday_pnl.max()
    worst_pnl = intraday_pnl.min()

    # TODO: calculate total P&L
    total_pnl = intraday_pnl.sum()
    return { 'intraday_PNL':intraday_pnl,
             'max_long_Position':max_long_position,
             'max_short_Position':max_short_position,
             'ending_Position':ending_position,
             'best_PNL':best_pnl,
             'worst_PNL':worst_pnl,
             'total_PNL':total_pnl }

# Get next order quantity
# TODO: figure out what our order size is
# TODO: start with some basic order size


    
# MAIN ALGO LOOP
def algo_loop( trading_day ):
    log_message( 'Beginning Tick Strategy run' )
    #log_message( 'TODO: remove this message. Simply a test to see how closely you are reading this code' )

    round_lot = 100
    avg_spread = ( trading_day.ask_px - trading_day.bid_px ).mean()
    half_spread = avg_spread / 2
    print( "Average stock spread for sample: {:.4f}".format(avg_spread) )

    # init our price and volume variables
    [ last_price, last_size, bid_price, bid_size, ask_price, ask_size, volume ] = np.zeros(7)
    
    # init some time series objects for collection of telemetry
    fair_values = pd.Series( index=trading_day.index )
    midpoints = pd.Series( index=trading_day.index )
    tick_factors = pd.Series( index=trading_day.index )
    risk_factors = pd.Series( index=trading_day.index )
    
    # let's set up a container to hold trades. preinitialize with the index
    trades = pd.DataFrame( columns = [ 'current_tick', 'stock_price', 'current_position', 'current_pnl', 'trade_price', 'trade_shares', 'trade_type', 'trade_side' ], index=trading_day.index )
    
    # MAIN EVENT LOOP
    live_order_index = trading_day.index[0]

    start_price = 0.0 # price when open the position
    prev_price = 0

    current_pos = 0.0
    trade_size = 100

    current_pnl = 0.0
    total_pnl = 0.0

    # track state and values for a current working order
    live_order = False
    live_order_price = 0.0
    live_order_quantity = 0.0
    order_side = '-'

    # other order and market variables

    # fair value pricing variables
    midpoint = 0.0
    fair_value = 0.0
    
    # define our accumulator for the tick EMA
    message_type = 0   
    tick_coef = 1
    tick_window = 20
    tick_factor = 0
    tick_ema_alpha = 2 / ( tick_window + 1 )
    prev_tick = 0
    this_tick = 0
    
    # risk factor for part 2
    # TODO: implement and evaluate 
    risk_factor = 0.0
    risk_coef = 0.0
    
    # signals
    tick_signal = 0

    log_message( 'starting main loop' )
    for index, row in trading_day.iterrows():
        # get the time of this message
        time_from_open = (index - pd.Timedelta( hours = 9, minutes = 30 ))
        minutes_from_open = (time_from_open.hour * 60) + time_from_open.minute
        
        # MARKET DATA HANDLING
        # When it's quote data
        if pd.isna( row.trade_px ): # it's a quote
            # skip if not NBBO
            if not ( ( row.qu_source == 'N' ) and ( row.natbbo_ind == 4 ) ):
                continue
            # set our local NBBO variables
            if ( row.bid_px > 0 and row.bid_size > 0 ):
                bid_price = row.bid_px
                #bid_size = row.bid_size * round_lot
            if ( row.ask_px > 0 and row.ask_size > 0 ):
                ask_price = row.ask_px
                #ask_size = row.ask_size * round_lot
                
            message_type = 'q'
                
        #When it's trade data
        else: # it's a trade
            # store the last trade price
            prev_price = last_price
            
            # now get the new data
            last_price = row.trade_px
            #last_size = row.trade_size
            
            message_type = 't'


            # CHECK OPEN ORDER(S) if we have a live order, 
            # has it been filled by the trade that just happened?
            if live_order :
                if (order_side == 'b') and (last_price <= live_order_price): #
                    
                    # even if we only got partially filled, let's assume the entire live order quantity can be filled. 
                    fill_size = live_order_quantity # = +100
                    
                    # update current position
                    current_pnl = current_pos * (live_order_price - start_price)
                    current_pos = current_pos + fill_size

                    # record trading data (previous index)
                    record_trade(trades, live_order_index, prev_tick, last_price, current_pos, current_pnl, live_order_price, fill_size, 'p', order_side)
                    total_pnl += current_pnl
                                     
                    # update start price
                    if current_pos > 0 :
                        start_price = live_order_price
                    elif current_pos == 0:
                        start_price = 0.0
                        
                    # deal with live order
                    live_order = False
                    live_order_price = 0.0
                    live_order_quantity = 0.0

                if (order_side == 's') and (last_price >= live_order_price):
                    
                    # even if we only got partially filled, let's assume the entire live order quantity can be filled. 
                    fill_size = live_order_quantity # = -100
                    
                    # update current position
                    current_pnl = current_pos * (live_order_price - start_price)
                    current_pos = current_pos + fill_size
                    
                    # record trading data
                    record_trade(trades, live_order_index, prev_tick, last_price, current_pos, current_pnl, live_order_price, fill_size, 'p', order_side)
                    total_pnl += current_pnl

                    # update start price
                    if current_pos < 0 :
                        start_price = live_order_price
                    elif current_pos == 0:
                        start_price = 0.0    

                    # deal with live order
                    live_order = False
                    live_order_price = 0.0
                    live_order_quantity = 0.0


            # TICK FACTOR
            # only update if it's a trade
            if message_type == 't':
                # calc the tick
                this_tick = np.sign(last_price - prev_price)
                if this_tick == 0:
                    this_tick = prev_tick

                # now calc the tick
                if tick_factor == 0:
                    tick_factor = this_tick
                else:
                    tick_factor = ( tick_ema_alpha * this_tick ) + ( 1 - tick_ema_alpha ) * tick_factor    

                # store the last tick
                prev_tick = this_tick

            # RISK FACTOR
            # TODO: For Part 2 Incorporate the Risk Factor

            # PRICING LOGIC
            new_midpoint = bid_price + ( ask_price - bid_price ) / 2
            if new_midpoint > 0:
                midpoint = new_midpoint

            # FAIR VALUE CALCULATION
            # check inputs, skip of the midpoint is zero, we've got bogus data (or we're at start of day)
            if midpoint == 0:
                #print( "{} no midpoint. b:{} a:{}".format( index, bid_price, ask_price ) )
                continue
            fair_value = midpoint + half_spread * ( ( tick_coef * tick_factor ) + ( risk_coef * risk_factor ) ) #tick_coef = 1


            # collect our data
            fair_values[ index ] = fair_value
            midpoints[ index ] = midpoint
            #tick_factors[ index ] = tick_factor
            # TODO: add collectors for new factors
            # risk_factors[ index ] =


            # TRADING LOGIC

            # update signal
            tick_signal = this_tick

            # TODO: determine if we want to buy or sell
            if (tick_signal == 1) and (current_pos <= 0): # if signal appears and we hold a short position or zero position, buy!
                order_side = 'b'

                # if fair price is > ask, buy agg
                if fair_value >= ask_price: 

                    new_trade_price = ask_price
                    new_trade_size = 1 * trade_size # = +100

                    # update P&L and position
                    current_pnl = current_pos * (new_trade_price - start_price)
                    current_pos = current_pos + new_trade_size # long shares to close previous short position or to open new position

                    # now place our aggressive order and record trade information
                    record_trade(trades, index, tick_signal, last_price, current_pos, current_pnl, new_trade_price, new_trade_size, 'a', order_side)
                    total_pnl += current_pnl

                    # update start price
                    if current_pos > 0:
                        start_price = new_trade_price
                    elif current_pos == 0:
                        start_price = 0

                    # deal with live order
                    live_order_quantity = 0.0
                    live_order_price = 0.0
                    live_order = False

                else: # if fair price is > bid, buy passive
                    # update P&L
                    current_pnl = current_pos * (last_price - start_price)
                    record_trade(trades, index, tick_signal, last_price, current_pos, current_pnl, 0, 0)

                    # send limit order
                    live_order_index = index
                    live_order_price = fair_value
                    live_order_quantity = tick_signal * trade_size # = +100
                    live_order = True

            elif (tick_signal == -1) and (current_pos >= 0):
                order_side = 's'

                # if fair price is < bid, sell agg
                if fair_value <= bid_price:

                    new_trade_price = bid_price
                    new_trade_size = -1 * trade_size # = -100

                    # update P&L and position
                    current_pnl = current_pos * (new_trade_price - start_price)
                    current_pos = current_pos + new_trade_size # short shares to close previous long position or to open new position

                    # now place our aggressive order and record trade information
                    record_trade(trades, index, tick_signal, last_price, current_pos, current_pnl, new_trade_price, new_trade_size, 'a', order_side)
                    total_pnl += current_pnl

                    # update start price
                    if current_pos < 0:
                        start_price = new_trade_price
                    elif current_pos == 0:
                        start_price = 0

                    # deal with live order
                    live_order_quantity = 0.0
                    live_order_price = 0.0
                    live_order = False

                else: # if fair price is < ask, sell passive
                    # update P&L
                    current_pnl = current_pos * (last_price - start_price)
                    record_trade(trades, index, tick_signal, last_price, current_pos, current_pnl, 0, 0)

                    # send limit order
                    live_order_index = index
                    live_order_price = fair_value
                    live_order_quantity = tick_signal * trade_size # = -100
                    live_order = True

            else:
                # no order here. for now just continue
                current_pnl = current_pos * (last_price - start_price)
                record_trade(trades, index, tick_signal, last_price, current_pos, current_pnl, 0, 0)
                continue

        prev_index = index



            
    # looping done
    log_message( 'end simulation loop' )
    log_message( 'order analytics' )

    # Now, let's look at some stats
    trades = trades.dropna()

    log_message( 'Algo run complete.' )

    # assemble results and return
    # TODO: add P&L
    return { 'trades' : trades,
             'total_pnl' : total_pnl
           }