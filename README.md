# tradingtools

Suite of tools for real-time cryptocurrency market analysis.

<h2>flowmeter.py</h2>

<b>To Do:</b>
- Websockets/Candle acquisition on combobox selection
- Charting
- Orderbook display
- Change candle and orderbook websockets to use unified multiplexed websocket
- Formatting:
-- Percent
-- +/- prefix
-- Padding/Alignment
- Extra Variables:
-- VOLUME FLOW RATE DIFFERENTIAL
-- Avg. amount per trade (count normalizer)
- Add units to analysis GUI variables
- Highlight difference frame if more pos/neg than other two
- Integrate matplotlib for charting
- Add ws restart on error
- Add ws timer and restart at 24 hours

<b>Needs Testing:</b>
- Sliding frame of 1 min to calculate in real-time: [CHANGED TO FULL INTERVAL]
-- Buys/Sells per second
-- Volume per second
- Add KeyboardInterrupt handling to new flowmeter version
- Add callback function for combobox selections

<b>Done:</b>
- Add trade history acquisition and db population on startup before ws initialization
- Add backtest interval info to analysis documents
- Get small arrow up/down icons for last trade message
- Add flow rate variables to GUI
- Add background colors for GUI difference values when positive/negative

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
