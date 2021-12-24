from QuantConnect.Data.UniverseSelection import *
import pandas as pd
import numpy as np


class BuyOnGapModel(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2020, 12, 1)
        self.SetEndDate(2021, 12, 1)
        self.SetCash(100000)
        self.AddEquity("SPY", Resolution.Minute)

        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.CoarseFilter, self.FineFilter)
        self.universe = None

        self.long_leverage = 0.9
        self.short_leverage = -0.9

        self.rebalance_universe = True

        self.longs = []
        self.shorts = []

        self.Schedule.On(self.DateRules.MonthStart("SPY"), self.TimeRules.At(0, 0), Action(self.UniverseRebalance))
        self.Schedule.On(self.DateRules.MonthStart("SPY"), self.TimeRules.At(0, 0), Action(self.SetLeverage))
        self.Schedule.On(self.DateRules.EveryDay("SPY"), self.TimeRules.AfterMarketOpen("SPY", 6),
                         Action(self.AlphaIndicator))
        self.Schedule.On(self.DateRules.EveryDay("SPY"), self.TimeRules.AfterMarketOpen("SPY", 7), Action(self.Long))
        self.Schedule.On(self.DateRules.EveryDay("SPY"), self.TimeRules.AfterMarketOpen("SPY", 8), Action(self.Short))
        self.Schedule.On(self.DateRules.EveryDay("SPY"), self.TimeRules.BeforeMarketClose("SPY", 5), Action(self.Close))

    def OnData(self, data):
        pass

    def CoarseFilter(self, coarse):
        if self.rebalance_universe:
            sortedByDollarVolume = sorted(coarse, key=lambda x:
            x.DollarVolume, reverse=True)

            filtered = [x.Symbol for x in sortedByDollarVolume if
                        x.HasFundamentalData and
                        float(x.Price) > 5]

            return filtered[:200]
        else:
            return self.universe

    def FineFilter(self, fine):
        if self.rebalance_universe:
            filtered = [x for x in fine if
                        x.ValuationRatios.EVToEBITDA > 0]
            self.universe = [x.Symbol for x in fine]
            self.rebalance_universe = False
        return self.universe

    def UniverseRebalance(self):
        self.rebalance_universe = True

    def AlphaIndicator(self):
        if self.universe is None: return

        shortlist = []
        longlist = []

        history = self.History(self.universe, 90, Resolution.Daily)

        for i in self.universe:
            if str(i) in history.index.levels[0]:
                close_90 = history.loc[str(i)]['close']
                stock_ret = np.log(close_90 / close_90.shift(1))
                mean_ret = stock_ret.mean()
                std_ret = stock_ret.std()

                open = history.loc[str(i)]['open'][-1]
                low = history.loc[str(i)]['low'][-2]
                current_ret = np.log(open / low)

                if current_ret < mean_ret - std_ret:
                    ma_20 = close_90[-20:].mean()
                    if open > ma_20:
                        longlist.append(i)

                elif current_ret > mean_ret + std_ret:
                    ma_20 = close_90[-20:].mean()
                    if open < ma_20:
                        shortlist.append(i)

        self.longs = longlist
        self.shorts = shortlist

    def PortfolioWeightings(self):
        pass

    def SetLeverage(self):
        pri = self.History(["SPY"], 200, Resolution.Daily)
        pos_one = (pri.loc["SPY"]['close'][-1])
        pos_six = (pri.loc["SPY"]['close'][-75:].mean())
        SPY_velocity = (pos_one - pos_six) / 100
        if SPY_velocity > 0:
            self.long_leverage = 1.8
            self.short_leverage = -0.0
        else:
            self.long_leverage = 1.1
            self.short_leverage = -0.7

    def Close(self):
        if self.universe is None:
            return

        for symbol in self.Portfolio.Keys:
            if (symbol in self.longs or symbol in self.shorts):
                self.SetHoldings(symbol, 0)

    def Long(self):
        if (self.universe is None) or len(self.longs) == 0: return

        for symbol in self.longs:
            self.AddEquity(symbol, Resolution.Minute)
            self.SetHoldings(symbol, self.long_leverage / len(self.longs))

    def Short(self):
        if (self.universe is None) or len(self.shorts) == 0: return

        for symbol in self.shorts:
            self.AddEquity(symbol, Resolution.Minute)
            self.SetHoldings(symbol, self.short_leverage / len(self.shorts))

    def RiskManagement(self):
        pass

