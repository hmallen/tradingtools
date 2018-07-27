# tradingtools

Suite of tools for real-time cryptocurrency market analysis.

<h2>flowmeter.py</h2>

<b>To Do:</b>
- Check if rows automatically span if not all columns defined
- Get small arrow up/down icons for last trade message
- Sliding frame of 1 min to calculate in real-time:
-- Buys/Sells per second
-- Volume per second
- Add KeyboardInterrupt handling to new flowmeter version
- Add ws restart on error
- Add ws timer and restart at 24 hours

<b>Needs Testing:</b>
-

<b>Done:</b>
- Add trade history acquisition and db population on startup before ws initialization
- Add backtest interval info to analysis documents

<b>Later:</b>
- Calculate duration of missing data if more requested than available

<b>Analysis Features:</b>
- Total Volume
-- Buy
-- Sell
-- Total
- Trade Count
-- Buy
-- Sell
-- Total
- Price Average
-- Buy
-- Sell
-- Total
