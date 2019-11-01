#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct 29 14:05:20 2019

@author: Lindsey
"""

import datetime
import numpy as np
import pandas as pd
import time
import sys

from simtools import log_message

# Lee-Ready tick strategy simulator
def risk_facter_setting(position):
    if position <-200:
        return 0.5
    if position >200:
        return -0.5
    return 0
# Record a trade in our trade array
    

def record_trade( trade_df, idx, trade_px, fair_value, last_price,ave_price,order_quantity, 
                 order_side,position,real_pnl, unreal_pnl,trade_type ):
    #print( "Trade! {} {} {} {}".format( idx, trade_px, trade_qty, current_bar ) )
    trade_df.loc[ idx ] = [trade_px, last_price, fair_value,ave_price,order_quantity,
                order_side,position,real_pnl, unreal_pnl ,trade_type ]

    return

# TODO: calc P&L and other statistics
class trade_statistics:
    
    def __init__(self,t_count):
        self.count=0
        self.position =0
        self.real_pnl=0.0
        self.unreal_pnl=0.0
        self.ave_price=0.0
        self.real_pnls=pd.Series(index=t_count)
        self.unreal_pnls=pd.Series(index=t_count)
        self.positions=pd.Series(index=t_count)
   
    def statistics(self,order_side,order_quant,trade_price,market_price):
    
        if order_side == 'b':
            flag=1
        if order_side == 's':
            flag=-1

        new_position=self.position+flag*order_quant

        # sign of position not change (short still short, long still long)
        if self.position*new_position>0:

            # position decrease
            if abs(new_position)<abs(self.position):
                self.real_pnl += order_quant*(trade_price-self.ave_price)
                self.unreal_pnl=new_position*(market_price-self.ave_price)
            #position increase
            else:
                self.ave_price=(self.position*self.ave_price+flag*order_quant*trade_price)/new_position
                self.unreal_pnl=new_position*(market_price-self.ave_price)

        # flat position  
        elif new_position == 0:
            self.real_pnl += self.position*(trade_price-self.ave_price)
            self.ave_price = 0
            self.unreal_pnl = 0

        # reverse position 
        else: 
            self.real_pnl +=self.position*(trade_price-self.ave_price)
            self.ave_price = trade_price
            self.unreal_pnl = new_position*(market_price-self.ave_price)

        self.position=new_position
        self.real_pnls[self.count]=self.real_pnl
        self.unreal_pnls[self.count]=self.unreal_pnl   
        self.positions[self.count]=self.position
        self.count+=1 
        
        print('position',self.position,'unreal_pnl',"{0:.2f}".format(self.unreal_pnl),
              'real_pnl',"{0:.2f}".format(self.real_pnl),
              'ave_price',"{0:.2f}".format(self.ave_price))
        
    def result(self):
        return [self.position, self.real_pnl,self.unreal_pnl,self.ave_price ]
# Get next order quantity
# TODO: figure out what our order size is
# TODO: start with some basic order size
'''def calc_order_quantity( raw_order_qty, round_lot, qty_remaining ):
    if raw_order_qty >= round_lot: # round to nearest lot
        return np.around( int( raw_order_qty ), int( -1 * np.log10( round_lot ) ) )
    # our target quantity is small... are we almost done?
    elif qty_remaining < round_lot:
        # we're less than 1 lot from completion, set for full size
        return qty_remaining 
    # we shouldn't get here. If we do, something is weird
    else:
        return -1
'''
def calc_order_quantity():
    return 1
    
# MAIN ALGO LOOP
def algo_loop( trading_day ):
    log_message( 'Beginning Tick Strategy run' )
    log_message( 'TODO: remove this message. Simply a test to see how closely you are reading this code' )

    round_lot = 100
    avg_spread = ( trading_day.ask_px - trading_day.bid_px ).mean()
    half_spread = avg_spread / 2
    print( "Average stock spread for sample: {:.4f}".format(avg_spread) )

    # init our price and volume variables
    [ last_price, last_size, bid_price, bid_size, ask_price, ask_size, volume ] = np.zeros(7)

    # init our counters
    [ trade_count, quote_count, cumulative_volume ] = [ 0, 0, 0 ]
    
    # init some time series objects for collection of telemetry
    fair_values = pd.Series( index=trading_day.index )
    midpoints = pd.Series( index=trading_day.index )
    tick_factors = pd.Series( index=trading_day.index )
    
    # let's set up a container to hold trades. preinitialize with the index
    trades = pd.DataFrame( columns = [ 'trade_px', 'last_price',' fair_value','ave_price','order_quantity',
                                      'order_side','position','real_pnl', 
                                      'unreal_pnl','trade_type' ], index=trading_day.index )
        
    tds=trade_statistics(trading_day.index)
    # MAIN EVENT LOOP

    # track state and values for a current working order
    live_order = False
    live_order_price = 0.0
    live_order_quantity = 0.0
    order_side = '-'


    # fair value pricing variables
    midpoint = 0.0
    fair_value = 0.0
    
    # define our accumulator for the tick EMA
    message_type = 0   
    tick_coef = 0.5
    tick_window = 20
    tick_factor = 0
    tick_ema_alpha = 2 / ( tick_window + 1 )
    prev_tick = 0
    prev_price = 0
    
    # risk factor for part 2
    # TODO: implement and evaluate 
    risk_factor = 0.0
    risk_coef = 1

    log_message( 'starting main loop' )
    
    for index, row in trading_day.iterrows():
        # get the time of this message
        
        time_from_open = (index - pd.Timedelta( hours = 9, minutes = 30 ))
        minutes_from_open = (time_from_open.hour * 60) + time_from_open.minute
        if minutes_from_open > 389:
            continue
        
        # MARKET DATA HANDLING
        if pd.isna( row.trade_px ): # it's a quote
            # skip if not NBBO
            if not ( ( row.qu_source == 'N' ) and ( row.natbbo_ind == 4 ) ):
                continue
            # set our local NBBO variables
            if ( row.bid_px > 0 and row.bid_size > 0 ):
                bid_price = row.bid_px
                bid_size = row.bid_size * round_lot
            if ( row.ask_px > 0 and row.ask_size > 0 ):
                ask_price = row.ask_px
                ask_size = row.ask_size * round_lot
            quote_count += 1
            message_type = 'q'
       
        else: # it's a trade
            # store the last trade price
            prev_price = last_price
            # now get the new data
            last_price = row.trade_px
            last_size = row.trade_size
            trade_count += 1
            cumulative_volume += row.trade_size
            message_type = 't'

            # CHECK OPEN ORDER(S) if we have a live order, 
            # has it been filled by the trade that just happened?
                                       
            if live_order :    
                success=0
                print('live order in')
                print('live_order_price,last_price',live_order_price,last_price)
                
           
                if ( order_side == 'b' ) and ( last_price <= live_order_price ) :  
                    success=1
                if ( order_side == 's' ) and ( last_price >= live_order_price ) :
                    success=1
                print('order side, success',order_side, success)
                
                if success:
                    print('order_side,order_quantity,live_order_price,last_price',order_side,live_order_quantity,live_order_price,last_price)
                    tds.statistics(order_side,live_order_quantity,live_order_price,last_price)
                    [position,real_pnl, unreal_pnl,ave_price]=tds.result() 
                    record_trade(trades, index, live_order_price, last_price, fair_value,ave_price,live_order_quantity, 
                                 order_side,position,real_pnl, unreal_pnl,'Pas')    
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
        
        risk_factor=0
        #risk_facter_setting(tds.position)
        fair_value = midpoint + half_spread *  ( tick_coef * tick_factor )# + ( risk_coef * risk_factor ) )
        fair_value=round(fair_value,2)
        # collect our data
        fair_values[ index ] = fair_value
        midpoints[ index ] = midpoint
        tick_factors[ index ] = tick_factor
 
        
        # TRADING LOGIC
        # check where our FV is versus the BBO and constrain
        print('index',index)
        if message_type == 't':
            
           
            
            if this_tick == 1:
                order_side='b'
            else:
                order_side='s'
                
            print('tick',this_tick,order_side)
            print('ask_price,bid_price,fair_value,last_price',ask_price,bid_price,fair_value,last_price)
            
            trade_type='non'
            if order_side == 'b' :
                trade_price = ask_price
                
                if fair_value > ask_price:
                    trade_type='Agg'
                elif fair_value> bid_price:
                    trade_type='Pas'
                
                   
            elif order_side == 's':
                 trade_price = bid_price
                 
                 if fair_value < bid_price:
                    trade_type='Agg'                   
                 elif fair_value < ask_price:
                    trade_type='Pas'
           

            if trade_type == 'Pas':
                print('Pas',order_side)
                live_order_price = trade_price
                live_order_quantity = calc_order_quantity()
                live_order = True
                
                
            if trade_type == 'Agg':
                print('Agg',order_side,fair_value)
                order_quantity = calc_order_quantity( )      
                print('order_side,order_quantity,trade_price,last_price',order_side,order_quantity,trade_price,last_price)
                tds.statistics(order_side,order_quantity,trade_price,last_price)
                [position,real_pnl, unreal_pnl,ave_price]=tds.result() 
                record_trade(trades, index, trade_price, last_price, fair_value,ave_price,order_quantity, 
                             order_side,position,real_pnl, unreal_pnl,'Agg')  
                live_order_quantity = 0.0
                live_order_price = 0.0
                live_order = False
    
    # looping done
    log_message( 'end simulation loop' )
    log_message( 'order analytics' )

    # Now, let's look at some stats
    trades = trades.dropna()

    log_message( 'Algo run complete.' )
#    real_pnls=tds.real_pnls.dropna()
#    positions=tds.positions.dropna()
#    unreal_pnls=tds.unreal_pnls.dropna()
    
    # assemble results and return
    # TODO: add P&L
    return { 'midpoints' : midpoints,
             'fair_values' : fair_values,
             'tick_factors' : tick_factors,
             'trades' : trades,
             'quote_count' : quote_count,

            
           }