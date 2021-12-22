from QuantConnect.Data.UniverseSelection import *
import pandas as pd
import numpy as np


class MeanReversionAlgorithmFramework(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2021, 6, 15)  # Set Start Date
        self.SetCash(100000)  # Set Strategy Cash
        self.AddUniverse(self.CoarseFilter, self.FineFilter)
        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddEquity("SPY", Resolution.Minute)

        self.universe = None

        self.long_leverage = 0.0
        self.short_leverage = -0.0

        self.rebalance_universe = True

        self.Schedule.On(self.DateRules.MonthStart("SPY"), self.TimeRules.At(0, 0), Action(self.Monthly_Rebalance))
        self.Schedule.On(self.DateRules.MonthStart("SPY"), self.TimeRules.At(0, 0), Action(self.set_leverage))
        self.Schedule.On(self.DateRules.EveryDay("SPY"), self.TimeRules.AfterMarketOpen("SPY", 1),
                         Action(self.get_prices))
        self.Schedule.On(self.DateRules.EveryDay("SPY"), self.TimeRules.AfterMarketOpen("SPY", 2),
                         Action(self.daily_rebalance))
        self.Schedule.On(self.DateRules.EveryDay("SPY"), self.TimeRules.AfterMarketOpen("SPY", 3), Action(self.short))
        self.Schedule.On(self.DateRules.EveryDay("SPY"), self.TimeRules.AfterMarketOpen("SPY", 4), Action(self.long))

    def OnData(self, data):
        pass

    def Monthly_Rebalance(self):
        self.rebalance_universe = True

    def CoarseFilter(self, coarse):
        if self.rebalance_universe:
            sortedByDollarVolume = sorted(coarse, key=lambda x:
            x.DollarVolume, reverse=True)

            filtered = [x.Symbol for x in sortedByDollarVolume
                        if float(x.Price) > 10 and
                        x.DollarVolume > 10000 and
                        x.HasFundamentalData]
            return filtered[:50]
        else:
            return self.universe

    def FineFilter(self, fine):
        if self.rebalance_universe:
            filtered = [x for x in fine if x.ValuationRatios.EVToEBITDA > 0]
            self.universe = [x.Symbol for x in filtered]
            self.rebalance_universe = False
        return self.universe

    def set_leverage(self):
        pri = self.History(["SPY"], 200, Resolution.Daily)
        pos_one = (pri.loc["SPY"]['close'][-1])
        pos_six = (pri.loc["SPY"]['close'][-75:])
        SPY_velocity = (pos_one - pos_six) / 100
        if SPY_velocity > 0:
            self.long_leverage = 1.8
            self.short_leverage = -0.0
        else:
            self.long_leverage = 1.1
            self.short_leverage = -0.7

    def long(self):
        if self.universe is None or len(self.longlist) + self.existinglong == 0: return

        for symbol in self.longlist:
            self.AddEquity(symbol, Resolution.Minute)
            self.SetHoldings(symbol, self.long_leverage / (len(self.longlist) + self.existinglong))

    def short(self):
        if self.universe is None or len(self.shortlist) + self.existingshort == 0: return

        for symbol in self.shortlist:
            self.AddEquity(symbol, Resolution.Minute)
            self.SetHoldings(symbol, self.short_leverage / (len(self.shortlist) + self.existingshort))

    def get_prices(self):
        if self.universe is None: return

        prices = {}
        hist = self.History(self.universe, 6, Resolution.Daily)
        for i in self.universe:
            if str(i) in hist.index.levels[0]:
                prices[i.Value] = hist.loc[str(i)]['close']
        df_prices = pd.DataFrame(prices, columns=prices.keys())

        daily_rets = np.log(df_prices / df_prices.shift(1))
        stdevs = daily_rets.std(axis=0)

        self.ret_qt = pd.qcut(daily_rets, 5, labels=False) + 1
        self.stdevs_qt = pd.qcut(stdevs, 3, labels=False) + 1
        self.longlist = list((self.ret_qt[self.ret_qt == 1].index) & (self.stdev_qt[self.stdev_qt < 3].index))
        self.shortlist = list((self.ret_qt[self.ret_qt == 5].index) & (self.stdev_qt[self.stdev_qt < 3].index))

    def daily_rebalance(self):
        if self.universe is None: return
        self.existingshort = 0
        self.existinglong = 0

        for symbol in self.Portfolio.Keys:
            if (symbol.Value != 'SPY') and (symbol.Value in self.ret_qt.index):
                current_quantile = self.ret_qt.loc[symbol.Value]
                if self.Portfolio[symbol].Quantity > 0:
                    if (current_quantile == 1) and symbol not in self.longlist:
                        self.existinglong += 1
                    elif (current_quantile > 1) and symbol not in self.shortlist:
                        self.SetHoldings(symbol, 0)
                elif self.Portfolio[symbol].Quantity < 0:
                    if (current_quantile == 5) and symbol not in self.shortlist:
                        self.existingshort += 1
                    elif current_quantile < 5 and symbol not in self.longlist:
                        self.SetHoldings(symbol, 0)
