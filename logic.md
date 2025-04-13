# 計算邏輯

本節說明了根據用戶輸入股票代碼推薦看漲與看跌期權的流程。該流程包含以下步驟：計算歷史波動率、擷取與篩選期權資料、利用布萊克－史科爾斯模型計算期權理論價格、從中挑選出符合理論價格上限且為價外（OTM）的期權，最後將結果以結構化的 JSON 格式回傳。

## 步驟 1：計算歷史波動率

- **目標**：根據近期價格資料估計股票波動性。  
- **方法**：
  - 透過 yfinance 擷取該股票過去 30 天的歷史資料，取得每日收盤價。  
  - 利用連續兩天收盤價之對數比值計算每日對數報酬率：  
    ```
    r_t = ln(P_t / P_{t-1})
    ```
    其中 `P_t` 代表第 t 天的收盤價。  
  - 計算所有報酬率的標準差，得到每日波動率 `σ_daily`。  
  - 將每日波動率年化：  
    ```
    σ_annual = σ_daily × √252
    ```
    （假設一年有 252 個交易日）。

## 步驟 2：擷取與篩選期權資料

- **目標**：取得符合流動性與到期日條件的期權資料。  
- **方法**：
  - 擷取股票期權的所有可用到期日。  
  - 根據用戶設定的最短持有天數（預設為 5 天）計算最早有效到期日，實際上依據計算公式為：
    ```
    min_expiration = 今日日期 + (min_days × 7 / 5) 天
    ```
    （例如預設 5 天會約等於 7 天後的到期）。  
  - 對每個符合條件的到期日，取得完整的期權鏈資料，包括看漲與看跌期權。  
  - 根據用戶設定的流動性條件（預設成交量大於 10，未平倉量大於 10）進行篩選，確保期權為活躍交易狀態。

## 步驟 3：計算期權的理論價格

- **目標**：利用布萊克－史科爾斯模型（Black-Scholes Model）來評估每個期權的公允價格。  
- **方法**：
  - 對每一筆篩選後的期權資料，傳入以下參數至布萊克－史科爾斯公式：
    - 當前股票價格 `S`（使用最新交易日收盤價取得）  
    - 行使價 `K`  
    - 到期時間 `T`（以年計，透過計算到期日與目前日期相差的天數除以 365）  
    - 無風險利率 `r`，由 yfinance 擷取 10 年期美國國債殖利率（如無資料則預設 1%）  
    - 年化波動率 `σ_annual`
  - **看漲期權公式**：
    ```
    C = S × N(d1) - K × e^(-rT) × N(d2)
    ```
  - **看跌期權公式**：
    ```
    P = K × e^(-rT) × N(-d2) - S × N(-d1)
    ```
  - 其中計算參數：
    ```
    d1 = [ln(S/K) + (r + σ²/2) × T] / (σ × √T)
    d2 = d1 - σ × √T
    ```
    且 `N(·)` 為標準常態分佈之累積分佈函數。  
  - 篩選出理論價格小於等於 2 美元的期權。

## 步驟 4：選擇推薦的期權

- **目標**：從篩選結果中挑選價外（OTM）的期權。  
- **方法**：
  - **看漲期權**：從所有理論價格 ≤ 2 美元且行使價 `K > S` 的候選中，挑選行使價與當前股票價格 `S` 差距最小者。  
  - **看跌期權**：從所有理論價格 ≤ 2 美元且行使價 `K < S` 的候選中，挑選與 `S` 差距最小者。  
  - 此篩選可協助選出價格較貼近現貨價格的 OTM 期權。

## 步驟 5：結果整理與回傳

- **目標**：以結構化格式回傳所選期權的詳細資訊。  
- **方法**：
  - 對於選定的看漲期權和看跌期權，分別整理出以下欄位資料：
    - **描述**：格式為 `MM/DD/YY Call` 或 `MM/DD/YY Put`（日期使用期權到期日格式化呈現）。  
    - 賣出價 (ask)、買入價 (bid) 與最近成交價 (lastPrice)。  
    - 行使價 (strike) 與到期日 (expiration)。
    - 理論價格 (theoretical_price)。
  - 除期權資料外，同時回傳一筆計算摘要，包括：
    - 無風險利率 `r`  
    - 年化波動率 `σ_annual`  
    - 當前股票價格 `S`
  - 最後將上述結果以 JSON 格式透過 API 端點回傳。

---

# Calculation Logic

This section explains the process for recommending call and put options based on the user-provided stock ticker. The process comprises the following steps: calculating historical volatility, fetching and filtering options data, computing theoretical option prices using the Black-Scholes model, selecting out-of-the-money (OTM) options that satisfy a maximum theoretical price, and finally returning the results in a structured JSON format.

## Step 1: Calculate Historical Volatility

- **Objective**: Estimate the stock’s volatility based on recent price movements.
- **Method**:
  - Retrieve historical data for the stock over the past 30 days using yfinance to obtain daily closing prices.
  - Compute daily logarithmic returns:
    ```
    r_t = ln(P_t / P_{t-1})
    ```
    where `P_t` represents the closing price on day t.
  - Calculate the standard deviation of these returns to obtain the daily volatility (`σ_daily`).
  - Annualize the daily volatility as:
    ```
    σ_annual = σ_daily × √252
    ```
    (assuming 252 trading days per year).

## Step 2: Fetch and Filter Options Data

- **Objective**: Obtain relevant options data that meet liquidity and expiration criteria.
- **Method**:
  - Fetch all available expiration dates for the stock’s options.
  - Filter the expiration dates to include only those at least a certain period away. Based on the user input (default is 5 days), the effective minimum expiration date is calculated as:
    ```
    min_expiration = Current Date + (min_days × 7 / 5) days
    ```
    (For example, the default of 5 days roughly translates to an expiration at least 7 days later).
  - For each valid expiration date, retrieve the complete options chain including both calls and puts.
  - Apply liquidity filters based on user settings (default: volume > 10 and open interest > 10) to ensure the options are actively traded.

## Step 3: Calculate Theoretical Option Prices

- **Objective**: Determine the fair value of each option using the Black-Scholes model.
- **Method**:
  - For each filtered option, use the Black-Scholes formula with the following parameters:
    - Current stock price `S` (retrieved from the latest trading day’s close)  
    - Strike price `K`  
    - Time to expiration `T` (in years, computed by the difference between the expiration date and current date divided by 365)  
    - Risk-free interest rate `r`, fetched from the 10-year U.S. Treasury yield (defaulting to 1% if unavailable)  
    - Annualized volatility `σ_annual`
  - **Call Option Formula**:
    ```
    C = S × N(d1) - K × e^(-rT) × N(d2)
    ```
  - **Put Option Formula**:
    ```
    P = K × e^(-rT) × N(-d2) - S × N(-d1)
    ```
  - Where:
    ```
    d1 = [ln(S/K) + (r + σ²/2) × T] / (σ × √T)
    d2 = d1 - σ × √T
    ```
    and `N(·)` is the cumulative distribution function of the standard normal distribution.
  - Only options with a theoretical price ≤ $2 are retained.

## Step 4: Select Recommended Options

- **Objective**: Identify out-of-the-money (OTM) options from the filtered set.
- **Method**:
  - **Call Options**: From the options with theoretical price ≤ $2 and strike price `K > S`, select the one whose strike is closest to the current stock price `S`.  
  - **Put Options**: From the options with theoretical price ≤ $2 and strike price `K < S`, select the one with the strike closest to `S`.

## Step 5: Result Compilation and Return

- **Objective**: Return the recommended option details in a structured format.
- **Method**:
  - For the selected call and put options, compile the following details:
    - **Description**: Formatted as `MM/DD/YY Call` or `MM/DD/YY Put` (using the formatted expiration date).  
    - Ask price, bid price, and the last traded price (`lastPrice`).  
    - Strike price and expiration date.
    - Theoretical price.
  - Additionally, include a calculation summary containing:
    - Risk-free rate `r`  
    - Annualized volatility `σ_annual`  
    - Current stock price `S`
  - The final results are returned via the API endpoint in a JSON format.
