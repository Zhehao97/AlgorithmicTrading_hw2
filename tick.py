import datetime
import numpy as np
import pandas as pd
import time
import sys

from simtools import log_message

# Lee-Ready tick strategy simulator

def sigmoid(x):
    return 2/(1 + np.exp(-x)) - 1

# Record a trade in our trade array
def record_trade( trade_df, idx, tick, risk, fair_value, market_price, trade_price, avg_price, position, unrealized_pnl, realized_pnl, trade_shares, trade_type, trade_side ):
    # fill in the table
    trade_df.loc[ idx ] = [ tick, risk, fair_value, market_price, trade_price, avg_price, position, unrealized_pnl, realized_pnl, trade_shares, trade_type, trade_side ]
    return

def calculate_unrealized_pnl(position, last_price, avg_price):
    return position * (last_price - avg_price)

def calculate_realized_pnl(realized_pnl, trade_size, order_price, avg_price):
    realized_pnl = realized_pnl + trade_size * (order_price - avg_price)
    return realized_pnl

# TODO: calc P&L and other statistics
def trade_statistics( trade_df ):

    # TODO: calculate intraday P&L (time series). P&L has two components. Roughly:
    #       1. realized "round trip" P&L  sum of (sell price - buy price) * shares traded
    #       2. unrealized P&L of open position:  quantity held * (current price - avg price)
    intraday_pnl = trade_df[['position', 'unrealized_pnl', 'realized_pnl']]

    # TODO: calculate maximum position (both long and short) and ending position
    max_long_position = trade_df['position'].max()
    max_short_position = trade_df['position'].min()
    ending_position = trade_df['position'][-1]

    # TODO: calculate worst and best intraday P&L
    best_unrealized_pnl = trade_df['unrealized_pnl'].max()
    worst_unrealized_pnl = trade_df['unrealized_pnl'].min()

    # TODO: calculate total P&L
    total_pnl = trade_df['realized_pnl'][-1]

    return { 'PNL':intraday_pnl,
             'max_long_Position':max_long_position,
             'max_short_Position':max_short_position,
             'ending_Position':ending_position,
             'best_unrealized_PNL':best_unrealized_pnl,
             'worst_unrealized_PNL':worst_unrealized_pnl,
             'total_realized_PNL':total_pnl
             }

# Get next order quantity
# TODO: figure out what our order size is
# TODO: start with some basic order size


    
# MAIN ALGO LOOP
def algo_loop( trading_day, risk_adj = 0, risk_denominator=1, tick_coef = 1, tick_window = 20 ):
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
    #tick_factors = pd.Series( index=trading_day.index )
    #risk_factors = pd.Series( index=trading_day.index )
    
    # let's set up a container to hold trades. preinitialize with the index
    trades = pd.DataFrame( columns = [ 'tick', 'risk', 'fair_value', 'market_price', 'trade_price', 'avg_price', 'position', 'unrealized_pnl', 'realized_pnl', 'trade_shares', 'trade_type', 'trade_side' ], index=trading_day.index )
    
    # MAIN EVENT LOOP
    trade_count = 0
    order_type = '-'
    order_side = '-'

    avg_price = 0.0

    previous_pos = 0
    current_pos = 0
    trade_size = 1

    unrealized_pnl = 0.0
    realized_pnl = 0.0

    # track state and values for a current working order
    live_order = False
    live_order_price = 0.0
    live_order_quantity = 0.0

    # other order and market variables

    # fair value pricing variables
    midpoint = 0.0
    fair_value = 0.0
    
    # define our accumulator for the tick EMA
    message_type = 0   
    tick_coef = 1.0
    tick_window = 20
    tick_factor = 0
    tick_ema_alpha = 2 / ( tick_window + 1 )
    prev_tick = 0
    this_tick = 0
    
    # risk factor for part 2
    # TODO: implement and evaluate 
    risk_factor = 0.0
    risk_coef = -1.0
    risk_window = 20
    risk_ema_alpha = 2 / ( risk_window + 1 )
    prev_risk = 0
    this_risk = 0
    
    # signals
    signal: int = 0

    log_message( 'starting main loop' )
    for index, row in trading_day.iterrows():

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
            last_size = row.trade_size
            
            message_type = 't'

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


            # TODO: For Part 2 Incorporate the Risk Factor
            # RISK FACTOR
            # use sigmoid function to map any real number to the range(-1,1)
            if message_type == 't' and risk_adj == 1:
                # call the risk
                this_risk = sigmoid(current_pos * avg_price / risk_denominator)
                if this_risk == 0:
                    this_risk = prev_risk

                # now calculate the risk factor
                if risk_factor == 0:
                    risk_factor = this_risk
                else:
                    risk_factor = ( risk_ema_alpha * this_risk ) + ( 1 - risk_ema_alpha ) * risk_factor

                #store the last risk
                prev_risk = this_risk


            # PRICING LOGIC
            new_midpoint = bid_price + ( ask_price - bid_price ) / 2
            if new_midpoint > 0:
                midpoint = new_midpoint

            # FAIR VALUE CALCULATION
            # check inputs, skip of the midpoint is zero, we've got bogus data (or we're at start of day)
            if midpoint == 0:
                continue
            fair_value = midpoint + half_spread * ( ( tick_coef * tick_factor ) + ( risk_coef * risk_factor ) )


            # collect our data
            # fair_values[ index ] = fair_value
            # midpoints[ index ] = midpoint
            # tick_factors[ index ] = tick_factor
            # TODO: add collectors for new factors


            # TRADING LOGIC

            # update signal
            signal = np.sign(last_price - prev_price)

            # LONG POSITION
            if current_pos > 0: # long position

                # CHECK for live limit order first
                if live_order:
                    if (order_side == 'b') and (last_price <= live_order_price):
                        order_type = 'Pas'

                        # update P&L
                        unrealized_pnl = current_pos * (last_price - avg_price)
                        # realized_pnl unchanged

                        # update position
                        previous_pos = current_pos
                        current_pos = current_pos + live_order_quantity

                        # update avg(buy) price
                        avg_price = ( previous_pos * avg_price + live_order_quantity * live_order_price ) / current_pos


                        # now place our aggressive order and record trade information
                        record_trade(trade_df=trades, idx=index, tick=signal, risk=risk_factor, fair_value=fair_value,  market_price=last_price, trade_price=live_order_price, avg_price=avg_price,
                                     position=current_pos, unrealized_pnl=unrealized_pnl, realized_pnl=realized_pnl,trade_shares=trade_size,
                                     trade_type=order_type, trade_side=order_side)

                        # deal with live order
                        live_order_quantity = 0.0
                        live_order_price = 0.0
                        live_order = False

                        continue

                    elif (order_side == 's') and (last_price >= live_order_price):
                        order_type = 'Pas'

                        # update P&L
                        unrealized_pnl = calculate_unrealized_pnl(position=current_pos, last_price=last_price, avg_price=avg_price)
                        realized_pnl = calculate_realized_pnl(realized_pnl=realized_pnl, trade_size=trade_size, order_price=live_order_price, avg_price=avg_price)

                        # update position
                        current_pos = current_pos - live_order_quantity

                        # avg(buy) price unchanged

                        # now place our aggressive order and record trade information
                        record_trade(trade_df=trades, idx=index, tick=signal, risk=risk_factor, fair_value=fair_value,  market_price=last_price, trade_price=live_order_price, avg_price=avg_price,
                                     position=current_pos, unrealized_pnl=unrealized_pnl, realized_pnl=realized_pnl,trade_shares=trade_size,
                                     trade_type=order_type, trade_side=order_side)

                        # deal with live order
                        live_order = False
                        live_order_price = 0.0
                        live_order_quantity = 0.0

                        continue

                # TODO: determine if we want to buy or sell
                if signal == 1: # if signal appears and we hold a short position or zero position, buy!
                    order_side = 'b'

                    # if fair price is > ask, buy agg
                    if fair_value >= ask_price:
                        order_type = 'Agg'
                        # trade_price = ask_price ;  trade_size = +100

                        # update P&L
                        unrealized_pnl = calculate_unrealized_pnl(position=current_pos, last_price=last_price, avg_price=avg_price)
                        # realized_pnl unchanged

                        # update position
                        previous_pos = current_pos
                        current_pos = current_pos + trade_size

                        # update avg(buy) price
                        avg_price = ( previous_pos * avg_price + trade_size * ask_price ) / current_pos

                        # now place our aggressive order and record trade information
                        record_trade(trade_df=trades, idx=index, tick=signal, risk=risk_factor, fair_value=fair_value,  market_price=last_price, trade_price=ask_price, avg_price=avg_price,
                                     position=current_pos, unrealized_pnl=unrealized_pnl, realized_pnl=realized_pnl,trade_shares=trade_size,
                                     trade_type=order_type, trade_side=order_side)

                        # deal with live order
                        live_order_quantity = 0.0
                        live_order_price = 0.0
                        live_order = False

                    # if fair price is > bid, buy passive
                    else:
                        # order_type = 'Pas'
                        # position unchanged

                        # avg(buy) price unchanged

                        # update P&L
                        # unrealized_pnl = current_pos * (last_price - avg_price)
                        # realized_pnl unchanged

                        # don't need to record trade information

                        # send limit order
                        live_order_quantity = 1 * trade_size  # = +100
                        live_order_price = bid_price
                        live_order = True

                elif signal == -1:
                    order_side = 's'

                    # if fair price is < bid, sell agg
                    if fair_value <= bid_price:
                        order_type = 'Agg'
                        # trade_price = bid_price ; trade_size = -100

                        # update P&L
                        unrealized_pnl = calculate_unrealized_pnl(position=current_pos, last_price=last_price, avg_price=avg_price)
                        realized_pnl = calculate_realized_pnl(realized_pnl=realized_pnl, trade_size=trade_size, order_price=bid_price, avg_price=avg_price)

                        # update position
                        current_pos = current_pos - trade_size

                        # avg(buy) price unchanged

                        # now place our aggressive order and record trade information
                        record_trade(trade_df=trades, idx=index, tick=signal, risk=risk_factor, fair_value=fair_value,  market_price=last_price, trade_price=bid_price, avg_price=avg_price,
                                     position=current_pos, unrealized_pnl=unrealized_pnl, realized_pnl=realized_pnl,trade_shares=trade_size,
                                     trade_type=order_type, trade_side=order_side)

                        # deal with live order
                        live_order_quantity = 0.0
                        live_order_price = 0.0
                        live_order = False

                    # if fair price is < ask, sell passive
                    else:
                        # order_type = 'Pas'
                        # position unchanged

                        # avg(buy) price unchanged

                        # update P&L
                        # unrealized_pnl = calculate_unrealized_pnl(position=current_pos, last_price=last_price, avg_price=avg_price)
                        # realized_pnl unchanged

                        # don't need to record trade information

                        # send limit order
                        live_order_quantity = 1 * trade_size  # = 100
                        live_order_price = ask_price
                        live_order = True

                else: # signal = 0
                    continue

            # SHORT POSITION
            elif current_pos < 0: #short position

                # CHECK for live limit order first
                if live_order:
                    if (order_side == 'b') and (last_price <= live_order_price):
                        order_type = 'Pas'

                        # update P&L
                        unrealized_pnl = calculate_unrealized_pnl(position=current_pos, last_price=last_price, avg_price=avg_price)
                        realized_pnl = calculate_realized_pnl(realized_pnl=realized_pnl, trade_size=trade_size, order_price=live_order_price, avg_price=avg_price)

                        # update position
                        current_pos = current_pos + live_order_quantity

                        # avg(sell) price unchanged

                        # now place our aggressive order and record trade information
                        record_trade(trade_df=trades, idx=index, tick=signal, risk=risk_factor, fair_value=fair_value,  market_price=last_price, trade_price=live_order_price, avg_price=avg_price,
                                     position=current_pos, unrealized_pnl=unrealized_pnl, realized_pnl=realized_pnl,trade_shares=trade_size,
                                     trade_type=order_type, trade_side=order_side)

                        # deal with live order
                        live_order_quantity = 0.0
                        live_order_price = 0.0
                        live_order = False

                        continue

                    elif (order_side == 's') and (last_price >= live_order_price):
                        order_type = 'Pas'

                        # update P&L
                        unrealized_pnl = calculate_unrealized_pnl(position=current_pos, last_price=last_price, avg_price=avg_price)
                        # realized_pnl unchanged

                        # update position
                        previous_pos = current_pos
                        current_pos = current_pos - live_order_quantity

                        # update avg(buy) price
                        avg_price = (previous_pos * avg_price - live_order_quantity * live_order_price) / current_pos

                        # now place our aggressive order and record trade information
                        record_trade(trade_df=trades, idx=index, tick=signal, risk=risk_factor, fair_value=fair_value,  market_price=last_price, trade_price=live_order_price, avg_price=avg_price,
                                     position=current_pos, unrealized_pnl=unrealized_pnl, realized_pnl=realized_pnl,trade_shares=trade_size,
                                     trade_type=order_type, trade_side=order_side)

                        # deal with live order
                        live_order = False
                        live_order_price = 0.0
                        live_order_quantity = 0.0

                        continue

                # TODO: determine if we want to buy or sell
                if signal == 1:  # if signal appears and we hold a short position or zero position, buy!
                    order_side = 'b'

                    # if fair price is > ask, buy agg
                    if fair_value >= ask_price:
                        order_type = 'Agg'
                        # trade_price = ask_price ; trade_size = +100

                        # update P&L
                        unrealized_pnl = calculate_unrealized_pnl(position=current_pos, last_price=last_price, avg_price=avg_price)
                        realized_pnl = calculate_realized_pnl(realized_pnl=realized_pnl, trade_size=trade_size, order_price=ask_price, avg_price=avg_price)

                        # update position
                        current_pos = current_pos + trade_size  # long shares to close previous short position or to open new position

                        # avg(sell) price unchanged

                        # now place our aggressive order and record trade information
                        record_trade(trade_df=trades, idx=index, tick=signal, risk=risk_factor, fair_value=fair_value,  market_price=last_price, trade_price=ask_price, avg_price=avg_price,
                                     position=current_pos, unrealized_pnl=unrealized_pnl, realized_pnl=realized_pnl,trade_shares=trade_size,
                                     trade_type=order_type, trade_side=order_side)

                        # deal with live order
                        live_order_quantity = 0.0
                        live_order_price = 0.0
                        live_order = False

                    # if fair price is > bid, buy passive
                    else:
                        # order_type = 'Pas'
                        # position unchanged

                        # avg(buy) price unchanged

                        # update P&L
                        # unrealized_pnl = calculate_unrealized_pnl(position=current_pos, last_price=last_price, avg_price=avg_price)
                        # realized_pnl unchanged

                        # don't need to record trade information

                        # send limit order
                        live_order_quantity = 1 * trade_size  # = +100
                        live_order_price = bid_price
                        live_order = True

                elif signal == -1:
                    order_side = 's'

                    # if fair price is < bid, sell agg
                    if fair_value <= bid_price:
                        order_type = 'Agg'
                        # trade_price = bid_price ; trade_size = -100

                        # update P&L
                        unrealized_pnl = calculate_unrealized_pnl(position=current_pos, last_price=last_price, avg_price=avg_price)
                        # realized_pnl unchanged

                        # update position
                        previous_pos = current_pos
                        current_pos = current_pos - trade_size

                        # update avg(buy) price
                        trade_count += 1
                        avg_price = (previous_pos * avg_price - trade_size * bid_price) / current_pos

                        # now place our aggressive order and record trade information
                        record_trade(trade_df=trades, idx=index, tick=signal, risk=risk_factor, fair_value=fair_value,  market_price=last_price, trade_price=bid_price, avg_price=avg_price,
                                     position=current_pos, unrealized_pnl=unrealized_pnl, realized_pnl=realized_pnl,trade_shares=trade_size,
                                     trade_type=order_type, trade_side=order_side)

                        # deal with live order
                        live_order_quantity = 0.0
                        live_order_price = 0.0
                        live_order = False

                    # if fair price is < ask, sell passive
                    else:
                        # order_type = 'Pas'
                        # position unchanged

                        # avg(buy) price unchanged

                        # update P&L
                        # unrealized_pnl = calculate_unrealized_pnl(position=current_pos, last_price=last_price, avg_price=avg_price)
                        # realized_pnl unchanged

                        # don't need to record trade information

                        # send limit order
                        live_order_quantity = 1 * trade_size  # = 100
                        live_order_price = ask_price
                        live_order = True

                else: # signal = 0
                    continue

            # ZERO POSITION
            else: # position = 0

                # clear the avg_price and trade_count
                avg_price = 0
                trade_count = 0

                # CHECK for live limit order first
                if live_order:
                    if (order_side == 'b') and (last_price <= live_order_price):
                        order_type = 'Pas'

                        # update P&L
                        unrealized_pnl = calculate_unrealized_pnl(position=current_pos, last_price=last_price, avg_price=avg_price)
                        # realized_pnl unchanged

                        # update position
                        previous_pos = current_pos
                        current_pos = current_pos + live_order_quantity

                        # update avg(buy) price
                        avg_price = ( previous_pos * avg_price + live_order_quantity * live_order_price ) / current_pos

                        # now place our aggressive order and record trade information
                        record_trade(trade_df=trades, idx=index, tick=signal, risk=risk_factor, fair_value=fair_value,  market_price=last_price, trade_price=live_order_price, avg_price=avg_price,
                                     position=current_pos, unrealized_pnl=unrealized_pnl, realized_pnl=realized_pnl,trade_shares=trade_size,
                                     trade_type=order_type, trade_side=order_side)

                        # deal with live order
                        live_order_quantity = 0.0
                        live_order_price = 0.0
                        live_order = False

                        continue

                    elif (order_side == 's') and (last_price >= live_order_price):
                        order_type = 'Pas'

                        # update P&L
                        unrealized_pnl = calculate_unrealized_pnl(position=current_pos, last_price=last_price, avg_price=avg_price)
                        # realized_pnl unchanged

                        # update position
                        previous_pos = current_pos
                        current_pos = current_pos - live_order_quantity

                        # update avg(buy) price
                        avg_price = (previous_pos * avg_price - live_order_quantity * live_order_price) / current_pos

                        # now place our aggressive order and record trade information
                        record_trade(trade_df=trades, idx=index, tick=signal, risk=risk_factor, fair_value=fair_value,  market_price=last_price, trade_price=live_order_price, avg_price=avg_price,
                                     position=current_pos, unrealized_pnl=unrealized_pnl, realized_pnl=realized_pnl,trade_shares=trade_size,
                                     trade_type=order_type, trade_side=order_side)

                        # deal with live order
                        live_order = False
                        live_order_price = 0.0
                        live_order_quantity = 0.0

                        continue

                # TODO: determine if we want to buy or sell
                if signal == 1: # if signal appears and we hold a short position or zero position, buy!
                    order_side = 'b'

                    # if fair price is > ask, buy agg
                    if fair_value >= ask_price:
                        order_type = 'Agg'
                        # trade_price = ask_price ;  trade_size = +100

                        # update P&L
                        unrealized_pnl = calculate_unrealized_pnl(position=current_pos, last_price=last_price, avg_price=avg_price)
                        # realized_pnl unchanged

                        # update position
                        previous_pos = current_pos
                        current_pos = current_pos + trade_size

                        #update avg(buy) price
                        avg_price = ( previous_pos * avg_price + trade_size * ask_price ) / current_pos

                        # now place our aggressive order and record trade information
                        record_trade(trade_df=trades, idx=index, tick=signal, risk=risk_factor, fair_value=fair_value,  market_price=last_price, trade_price=ask_price, avg_price=avg_price,
                                     position=current_pos, unrealized_pnl=unrealized_pnl, realized_pnl=realized_pnl,trade_shares=trade_size,
                                     trade_type=order_type, trade_side=order_side)

                        # deal with live order
                        live_order_quantity = 0.0
                        live_order_price = 0.0
                        live_order = False

                    # if fair price is > bid, buy passive
                    else:
                        # order_type = 'Pas'
                        # position unchanged

                        # avg(buy) price unchanged

                        # update P&L
                        # unrealized_pnl = current_pos * (last_price - avg_price)
                        # realized_pnl unchanged

                        # don't need to record trade information

                        # send limit order
                        live_order_quantity = 1 * trade_size  # = +100
                        live_order_price = bid_price
                        live_order = True

                elif signal == -1:
                    order_side = 's'

                    # if fair price is < bid, sell agg
                    if fair_value <= bid_price:
                        order_type = 'Agg'
                        # trade_price = bid_price ; trade_size = -100

                        # update P&L
                        unrealized_pnl = calculate_unrealized_pnl(position=current_pos, last_price=last_price, avg_price=avg_price)
                        # realized_pnl unchanged

                        # update position
                        previous_pos = current_pos
                        current_pos = current_pos - trade_size

                        # update avg(buy) price
                        avg_price = (previous_pos * avg_price - trade_size * bid_price) / current_pos

                        # now place our aggressive order and record trade information
                        record_trade(trade_df=trades, idx=index, tick=signal, risk=risk_factor, fair_value=fair_value,  market_price=last_price, trade_price=bid_price, avg_price=avg_price,
                                     position=current_pos, unrealized_pnl=unrealized_pnl, realized_pnl=realized_pnl,trade_shares=trade_size,
                                     trade_type=order_type, trade_side=order_side)

                        # deal with live order
                        live_order_quantity = 0.0
                        live_order_price = 0.0
                        live_order = False

                    else:
                        # order_type = 'Pas'
                        # position unchanged

                        # avg(buy) price unchanged

                        # update P&L
                        # unrealized_pnl = calculate_unrealized_pnl(position=current_pos, last_price=last_price, avg_price=avg_price)
                        # realized_pnl unchanged

                        # don't need to record trade information

                        # send limit order
                        live_order_quantity = 1 * trade_size  # = -100
                        live_order_price = ask_price
                        live_order = True
                        
                else: # signal = 0
                    continue

    # looping done
    log_message( 'end simulation loop' )
    log_message( 'order analytics' )

    # Now, let's look at some stats
    trades = trades.dropna()

    log_message( 'Algo run complete.' )

    # assemble results and return
    # TODO: add P&L
    return trades
