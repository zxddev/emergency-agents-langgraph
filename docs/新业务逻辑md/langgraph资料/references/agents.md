# Langgraph - Agents

**Pages:** 20

---

## Multi-agent network¶

**URL:** https://langchain-ai.github.io/langgraph/tutorials/multi_agent/multi-agent-collaboration/

**Contents:**
- Multi-agent network¶
- Setup¶
- Define tools¶
- Create graph¶
  - Define Agent Nodes¶
  - Define the Graph¶
- Invoke¶

A single agent can usually operate effectively using a handful of tools within a single domain, but even using powerful models like gpt-4, it can be less effective at using many tools.

One way to approach complicated tasks is through a "divide-and-conquer" approach: create a specialized agent for each task or domain and route tasks to the correct "expert". This is an example of a multi-agent network architecture.

This notebook (inspired by the paper AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation, by Wu, et. al.) shows one way to do this using LangGraph.

The resulting graph will look something like the following diagram:

Before we get started, a quick note: this and other multi-agent notebooks are designed to show how you can implement certain design patterns in LangGraph. If the pattern suits your needs, we recommend combining it with some of the other fundamental patterns described elsewhere in the docs for best performance.

First, let's install our required packages and set our API keys:

Set up LangSmith for LangGraph development

Sign up for LangSmith to quickly spot issues and improve the performance of your LangGraph projects. LangSmith lets you use trace data to debug, test, and monitor your LLM apps built with LangGraph — read more about how to get started here.

We will also define some tools that our agents will use in the future

API Reference: TavilySearch | tool | PythonREPL

Now that we've defined our tools and made some helper functions, will create the individual agents below and tell them how to talk to each other using LangGraph.

We now need to define the nodes.

First, we'll create a utility to create a system prompt for each agent.

API Reference: BaseMessage | HumanMessage | ChatAnthropic | create_react_agent | END | Command

We can now put it all together and define the graph!

API Reference: StateGraph | START

With the graph created, you can invoke it! Let's have it chart some stats for us.

events = graph.stream( { "messages": [ ( "user", "First, get the UK's GDP over the past 5 years, then make a line chart of it. " "Once you make the chart, finish.", ) ], }, # Maximum number of steps to take in the graph {"recursion_limit": 150}, ) for s in events: print(s) print("----") {'researcher': {'messages': [HumanMessage(content="First, get the UK's GDP over the past 5 years, then make a line chart of it. Once you make the chart, finish.", additional_kwargs={}, response_metadata={}, id='fa1f5e95-9e1a-47d4-b4b6-e93f345e339d'), AIMessage(content=[{'text': "I'll help search for the UK's GDP data over the past 5 years. Then my colleague can help create the line chart.", 'type': 'text'}, {'id': 'toolu_01Jd9dxa4Ss2NhzBhCuwUX3E', 'input': {'query': 'UK GDP annual data past 5 years 2019-2023'}, 'name': 'tavily_search_results_json', 'type': 'tool_use'}], additional_kwargs={}, response_metadata={'id': 'msg_014nCkfVHnG6LAsiS6pY7zcd', 'model': 'claude-3-5-sonnet-20241022', 'stop_reason': 'tool_use', 'stop_sequence': None, 'usage': {'input_tokens': 555, 'output_tokens': 101}}, id='run-e2297529-9972-4de6-835d-23d920b0e29b-0', tool_calls=[{'name': 'tavily_search_results_json', 'args': {'query': 'UK GDP annual data past 5 years 2019-2023'}, 'id': 'toolu_01Jd9dxa4Ss2NhzBhCuwUX3E', 'type': 'tool_call'}], usage_metadata={'input_tokens': 555, 'output_tokens': 101, 'total_tokens': 656, 'input_token_details': {}}), ToolMessage(content='[{"url": "https://www.macrotrends.net/global-metrics/countries/GBR/united-kingdom/gdp-gross-domestic-product", "content": "Dollar figures for GDP are converted from domestic currencies using single year official exchange rates. For a few countries where the official exchange rate does not reflect the rate effectively applied to actual foreign exchange transactions, an alternative conversion factor is used. U.K. gdp for 2023 was $3,340.03B, a 8.13% increase from 2022."}, {"url": "https://www.statista.com/topics/3795/gdp-of-the-uk/", "content": "Monthly growth of gross domestic product in the United Kingdom from January 2019 to November 2023\\nContribution to GDP growth in the UK 2023, by sector\\nContribution to gross domestic product growth in the United Kingdom in January 2023, by sector\\nGDP growth rate in the UK 1999-2021, by country\\nAnnual growth rates of gross domestic product in the United Kingdom from 1999 to 2021, by country\\nGDP growth rate in the UK 2021, by region\\nAnnual growth rates of gross domestic product in the United Kingdom in 2021, by region\\nGDP growth of Scotland 2021, by local area\\nAnnual growth rates of gross domestic product in Scotland in 2021, by local (ITL 3) area\\nGDP growth of Wales 2021, by local area\\nAnnual growth rates of gross domestic product in Wales in 2021, by local (ITL 3) area\\nGDP growth of Northern Ireland 2021, by local area\\nAnnual growth rates of gross domestic product in Northern Ireland in 2021, by local (ITL 3) area\\nGDP per capita\\nGDP per capita\\nGDP per capita in the UK 1955-2022\\nGross domestic product per capita in the United Kingdom from 1955 to 2022 (in GBP)\\nAnnual GDP per capita growth in the UK 1956-2022\\nAnnual GDP per capita growth in the United Kingdom from 1956 to 2022\\nQuarterly GDP per capita in the UK 2019-2023\\nQuarterly GDP per capita in the United Kingdom from 1st quarter 2019 to 3rd quarter 2023 (in GBP)\\nQuarterly GDP per capita growth in the UK 2019-2023\\nQuarterly GDP per capita growth in the United Kingdom from 1st quarter 2019 to 3rd quarter 2023 (in GBP)\\nGDP per capita of the UK 1999-2021, by country\\nGross domestic product per capita of the United Kingdom from 1999 to 2021, by country (in GBP)\\nGDP per capita of the UK 2021, by region\\nGross domestic product per capita of the United Kingdom in 2021, by region (in GBP)\\nGlobal Comparisons\\nGlobal Comparisons\\nCountries with the largest gross domestic product (GDP) 2022\\n Monthly GDP of the UK 2019-2023\\nMonthly index of gross domestic product in the United Kingdom from January 2019 to November 2023 (2019=100)\\nGVA of the UK 2022, by sector\\nGross value added of the United Kingdom in 2022, by industry sector (in million GBP)\\nGDP of the UK 2021, by country\\nGross domestic product of the United Kingdom in 2021, by country (in million GBP)\\nGDP of the UK 2021, by region\\nGross domestic product of the United Kingdom in 2021, by region (in million GBP)\\nGDP of Scotland 2021, by local area\\nGross domestic product of Scotland in 2021, by local (ITL 3) area (in million GBP)\\nGDP of Wales 2021, by local area\\nGross domestic product of Wales in 2021, by local (ITL 3) area (in million GBP)\\nGDP of Northern Ireland 2021, by local area\\nGross domestic product of Northern Ireland in 2021, by local (ITL 3) area (in million GBP)\\nGDP growth\\nGDP growth\\nGDP growth forecast for the UK 2000-2028\\nForecasted annual growth of gross domestic product in the United Kingdom from 2000 to 2028\\nAnnual GDP growth in the UK 1949-2022\\nAnnual growth of gross domestic product in the United Kingdom from 1949 to 2022\\nQuarterly GDP growth of the UK 2019-2023\\nQuarterly growth of gross domestic product in the United Kingdom from 1st quarter 2019 to 3rd quarter 2023\\nMonthly GDP growth of the UK 2019-2023\\n Transforming data into design:\\nStatista Content & Design\\nStrategy and business building for the data-driven economy:\\nUK GDP - Statistics & Facts\\nUK economy expected to shrink in 2023\\nCharacteristics of UK GDP\\nKey insights\\nDetailed statistics\\nGDP of the UK 1948-2022\\nDetailed statistics\\nAnnual GDP growth in the UK 1949-2022\\nDetailed statistics\\nGDP per capita in the UK 1955-2022\\nEditor’s Picks\\nCurrent statistics on this topic\\nCurrent statistics on this topic\\nKey Economic Indicators\\nMonthly GDP growth of the UK 2019-2023\\nKey Economic Indicators\\nMonthly GDP of the UK 2019-2023\\nKey Economic Indicators\\nContribution to GDP growth in the UK 2023, by sector\\nRelated topics\\nRecommended\\nRecommended statistics\\nGDP\\nGDP\\nGDP of the UK 1948-2022\\nGross domestic product of the United Kingdom from 1948 to 2022 (in million GBP)\\nQuarterly GDP of the UK 2019-2023\\nQuarterly gross domestic product in the United Kingdom from 1st quarter 2019 to 3rd quarter 2023 (in million GBP)\\n The 20 countries with the largest gross domestic product (GDP) in 2022 (in billion U.S. dollars)\\nGDP of European countries in 2022\\nGross domestic product at current market prices of selected European countries in 2022 (in million euros)\\nReal GDP growth rates in Europe 2023\\nAnnual real gross domestic product (GDP) growth rate in European countries in 2023\\nGross domestic product (GDP) of Europe\'s largest economies 1980-2028\\nGross domestic product (GDP) at current prices of Europe\'s largest economies from 1980 to 2028 (in billion U.S dollars)\\nUnited Kingdom\'s share of global gross domestic product (GDP) 2028\\nUnited Kingdom (UK): Share of global gross domestic product (GDP) adjusted for Purchasing Power Parity (PPP) from 2018 to 2028\\nRelated topics\\nRecommended\\nReport on the topic\\nKey figures\\nThe most important key figures provide you with a compact summary of the topic of \\"UK GDP\\" and take you straight to the corresponding statistics.\\n Industry Overview\\nDigital & Trend reports\\nOverview and forecasts on trending topics\\nIndustry & Market reports\\nIndustry and market insights and forecasts\\nCompanies & Products reports\\nKey figures and rankings about companies and products\\nConsumer & Brand reports\\nConsumer and brand insights and preferences in various industries\\nPolitics & Society reports\\nDetailed information about political and social topics\\nCountry & Region reports\\nAll key figures about countries and regions\\nMarket forecast and expert KPIs for 1000+ markets in 190+ countries & territories\\nInsights on consumer attitudes and behavior worldwide\\nBusiness information on 100m+ public and private companies\\nExplore Company Insights\\nDetailed information for 39,000+ online stores and marketplaces\\nDirectly accessible data for 170 industries from 150+ countries\\nand over 1\xa0Mio. facts.\\n"}, {"url": "https://data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG?locations=GB", "content": "GDP growth (annual %) - United Kingdom | Data - World Bank Data"}, {"url": "https://www.statista.com/topics/6500/the-british-economy/", "content": "Output per hour worked in the UK 1971 to 2023\\nEconomic output per hour worked in the United Kingdom from 1st quarter 1971 to 2nd quarter 2023 (2019=100)\\nAnnual unemployment rate in the UK 2000-2028\\nAnnual unemployment rate in the United Kingdom from 2000 to 2028\\nInflation\\nInflation\\nInflation rate in the UK 1989-2023\\nInflation rate for the Consumer Price Index (CPI) in the United Kingdom from January 1989 to October 2023\\nRPI inflation rate in the UK 1948-2023\\nInflation rate for the Retail Price Index (RPI) in the United Kingdom from June 1948 to October 2023\\nCPIH inflation rate in the UK 1989-2023\\nInflation rate for the Consumer Price Index including owner occupiers\' housing costs (CPIH) in the United Kingdom from January 1989 to October 2023\\nPPI in the UK 2010-2023\\nProducer Price Index (PPI) in the United Kingdom from October 2010 to October 2023\\nCPI inflation rate in the UK 2023, by sector\\nInflation rate for the Consumer Price Index (CPI) in the United Kingdom in October 2023, by sector\\nConsumer Price Index in the UK 1988-2023\\nConsumer Price Index (CPI) in the United Kingdom from 1st quarter 1988 to 3rd quarter 2023\\nRetail Price Index in the UK 1987-2023\\nRetail Price Index (RPI) in the United Kingdom from 1st quarter 1987 to 3rd quarter 2023\\nConsumer Price Index including housing in the UK 1988-2023\\nConsumer Price Index including owner occupiers\' housing costs (CPIH) in the United Kingdom from 1st quarter 1988 to 3rd quarter 2023\\nRPI annual inflation rate UK 2000-2028\\nAnnual inflation rate of the Retail Price Index in the United Kingdom from 2000 to 2028\\nCPI annual inflation rate UK 2000-2028\\nAnnual inflation rate of the Consumer Price Index in the United Kingdom from 2000 to 2028\\nGovernment finances\\nGovernment finances\\nGovernment spending as a percentage of GDP in the UK 1900-2029\\nTotal managed expenditure expressed as a percentage of GDP in the United Kingdom from 1900/01 to 2028/29\\nGovernment revenue as a percentage of GDP in the UK 1900-2029\\nTotal public sector current receipts expressed as a percentage of GDP in the United Kingdom from 1900/01 to 2028/29 (in million GBP)\\nGovernment borrowing as a percentage of GDP in the UK 1900-2029\\nPublic sector borrowing expressed as a percentage of GDP in the United Kingdom from 1900/01 to 2028/29\\nNational debt as a percentage of GDP in the UK 1900-2029\\nPublic sector net debt expressed as a percentage of GDP in the United Kingdom from 1900/01 to 2028/29\\nPublic sector spending in the United Kingdom 2023/24\\nBudgeted public sector expenditure on services in the United Kingdom in 2023/24, by function (in billion GBP)\\nGovernment revenue sources in the United Kingdom 2023/24\\nExpected public sector current receipts in the United Kingdom in 2023/24, by function (in billion GBP)\\nBusiness Enterprise\\nBusiness Enterprise\\nLargest companies in the United Kingdom based on revenue 2022\\nLargest companies in the United Kingdom based on revenue in 2022 (in billion US dollars)\\nLargest UK companies based on number of global employees 2020\\nLargest companies based in the United Kingdom on number of employees worldwide in 2020 (in 1,000s)\\nNumber of private sector businesses in the UK 2000-2023\\nNumber of private sector businesses in the United Kingdom from 2000 to 2023 (in millions)\\nNumber of private sector businesses in the UK 2023, by sector\\nNumber of private sector businesses in the United Kingdom in 2023, by sector\\nNumber of businesses by enterprise size in the UK 2023\\nNumber of private sector businesses in the United Kingdom in 2023, by employment size\\nNumber of private sector businesses in the UK 2023, by region\\nNumber of private sector businesses in the United Kingdom in 2023, by region\\nNumber of local business units in the UK 2012-2023\\nNumber of local units in VAT and/or PAYE based enterprises in the United Kingdom from 2012 to 2023 (in millions)\\nBusiness investment index in the UK 1997-2023\\nBusiness investment index in the United Kingdom from 1st quarter 1997 to 2nd quarter 2023 (Q1 1997=100)\\nBusiness confidence Index in the UK 1977-2023\\nBusiness confidence Index of the United Kingdom from March 1977 to November 2023 (100 = long-term average)\\nRelated topics\\nRecommended\\nReport on the topic\\nKey figures\\nThe most important key figures provide you with a compact summary of the topic of \\"The UK economy\\" and take you straight to the corresponding statistics.\\n Monthly GDP growth of the UK 2020-2023\\nMonthly growth of gross domestic product in the United Kingdom from January 2020 to September 2023\\nGDP of the UK 2021, by region\\nGross domestic product of the United Kingdom in 2021, by region (in million GBP)\\nGDP growth rate in the UK 2021, by region\\nAnnual growth rates of gross domestic product in the United Kingdom in 2021, by region\\nGDP per capita of the UK 2021, by region\\nGross domestic product per capita of the United Kingdom in 2021, by region (in GBP)\\nGDP growth forecast for the UK 2000-2028\\nForecasted annual growth of gross domestic product in the United Kingdom from 2000 to 2028\\nLabor Market\\nLabor Market\\nUnemployment rate of the UK 1971-2023\\nUnemployment rate in the United Kingdom from March 1971 to September 2023\\nEmployment rate in the UK 1971-2022\\nEmployment rate in the United Kingdom from March 1971 to July 2023\\nNumber of people unemployed in the UK 1971-2023\\nNumber of people unemployed in the United Kingdom from March 1971 to July 2023 (in 1,000s)\\nNumber of people employed in the UK 1971-2021\\nNumber of people employed in the United Kingdom from March 1971 to July 2023 (in 1,000s)\\nUnemployment rate in the UK 1971-2023, by gender\\nUnemployment rate in the United Kingdom from 1st quarter 1971 to 2nd quarter 2023, by gender\\nUnemployment rate in the UK 1992-2023, by age group\\nUnemployment rate in the United Kingdom from May 1992 to July 2023, by age group\\nYouth unemployment rate in the UK 1992-2023\\nYouth unemployment rate in the United Kingdom from May 1992 to July 2023\\nAverage annual earnings for full-time employees in the UK 1999-2023\\nMedian annual earnings for full-time employees in the United Kingdom from 1999 to 2023 (in nominal GBP)\\nAverage weekly earning growth in the UK 2001-2023\\nAverage year-on-year growth of weekly earnings (3 month average) in the United Kingdom from March 2001 to October 2023\\nNumber of redundancies in the UK 1995-2023\\nAverage number of people made redundant in the United Kingdom from May 1995 to July 2023 (in 1,000s)\\nOverall weekly hours worked in the UK 1971-2023\\nOverall weekly hours worked for all employees in the United Kingdom from 1st quarter 1971 to 2nd quarter 2023 (in million hours worked)\\n Transforming data into design:\\nStatista Content & Design\\nStrategy and business building for the data-driven economy:\\nThe UK economy - Statistics & Facts\\nUK households under pressure in 2023\\nCoronavirus devastates UK economy in 2020\\nKey insights\\nDetailed statistics\\nGDP of the UK 1948-2022\\nDetailed statistics\\nUnemployment rate of the UK 1971-2023\\nDetailed statistics\\nInflation rate in the UK 1989-2023\\nEditor’s Picks\\nCurrent statistics on this topic\\nCurrent statistics on this topic\\nWages & Salaries\\nAverage weekly earning growth in the UK 2001-2023\\nIncome & Expenditure\\nPublic sector spending in the United Kingdom 2023/24\\nEmployment\\nNumber of people employed in the UK 1971-2021\\nRelated topics\\nRecommended\\nRecommended statistics\\nGross domestic product\\nGross domestic product\\nGDP of the UK 1948-2022\\nGross domestic product of the United Kingdom from 1948 to 2022 (in million GBP)\\nAnnual GDP growth in the UK 1949-2022\\nAnnual growth of gross domestic product in the United Kingdom from 1949 to 2022\\nGDP per capita in the UK 1955-2022\\nGross domestic product per capita in the United Kingdom from 1955 to 2022 (in GBP)\\nQuarterly GDP of the UK 1955-2023\\nQuarterly gross domestic product in the United Kingdom from 1st quarter 1955 to 3rd quarter 2023 (in million GBP)\\nQuarterly GDP growth of the UK 2015-2023\\nQuarterly growth of gross domestic product in the United Kingdom from 1st quarter 2015 to 3rd quarter 2023\\nQuarterly GDP per capita in the UK 1955-2023\\nQuarterly GDP per capita in the United Kingdom from 1st quarter 1955 to 3rd quarter 2023 (in GBP)\\nMonthly GDP of the UK 1997-2023\\nMonthly index of gross domestic product in the United Kingdom from January 1997 to September 2023 (2019=100)\\n GDP\\nAnnual GDP growth in the UK 1949-2022\\nQuarterly GDP per capita growth in the UK 2015-2023\\nMonthly GDP growth of the UK 2020-2023\\nGDP per capita in the UK 1955-2022\\nLabor market\\nNumber of people employed in the UK 1971-2021\\nNumber of people unemployed in the UK 1971-2023\\nDaily number of jobs furloughed in the UK 2020-2021\\nAverage annual earnings for full-time employees in the UK 1999-2023\\nForecasts for 2023\\nGDP growth forecast for the UK 2000-2028\\nAnnual unemployment rate in the UK 2000-2028\\nCPI annual inflation rate UK 2000-2028\\nRPI annual inflation rate UK 2000-2028\\n Industry Overview\\nDigital & Trend reports\\nOverview and forecasts on trending topics\\nIndustry & Market reports\\nIndustry and market insights and forecasts\\nCompanies & Products reports\\nKey figures and rankings about companies and products\\nConsumer & Brand reports\\nConsumer and brand insights and preferences in various industries\\nPolitics & Society reports\\nDetailed information about political and social topics\\nCountry & Region reports\\nAll key figures about countries and regions\\nMarket forecast and expert KPIs for 1000+ markets in 190+ countries & territories\\nInsights on consumer attitudes and behavior worldwide\\nBusiness information on 100m+ public and private companies\\nExplore Company Insights\\nDetailed information for 39,000+ online stores and marketplaces\\nDirectly accessible data for 170 industries from 150+ countries\\nand over 1\xa0Mio. facts.\\n"}, {"url": "https://data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG?locations=GB&most_recent_value_desc=false", "content": "GDP growth (annual %) - United Kingdom | Data Data GDP growth (annual %)United Kingdom Data Catalog Data Programs International Debt Statistics Other Books and Reports For Developers GDP growth (annual %) - United Kingdom ====================================== Similar values Highest values Lowest values GDP (constant 2015 US$) GDP (current US$) GDP (constant LCU) GDP: linked series (current LCU) GDP, PPP (constant 2021 international $) GDP (current LCU) GDP, PPP (current international $) GDP per capita growth (annual %) Country Most Recent Value All Countries and Economies Country Most Recent Value This site uses cookies to optimize functionality and give you the best possible experience. If you continue to navigate this website beyond this page, cookies will be placed on your browser."}]', name='tavily_search_results_json', id='4c88089f-0ac4-4eeb-9141-722f0463b78d', tool_call_id='toolu_01Jd9dxa4Ss2NhzBhCuwUX3E', artifact={'query': 'UK GDP annual data past 5 years 2019-2023', 'follow_up_questions': None, 'answer': None, 'images': [], 'results': [{'title': 'U.K. GDP 1960-2024 - Macrotrends', 'url': 'https://www.macrotrends.net/global-metrics/countries/GBR/united-kingdom/gdp-gross-domestic-product', 'content': 'Dollar figures for GDP are converted from domestic currencies using single year official exchange rates. For a few countries where the official exchange rate does not reflect the rate effectively applied to actual foreign exchange transactions, an alternative conversion factor is used. U.K. gdp for 2023 was $3,340.03B, a 8.13% increase from 2022.', 'score': 0.97675806, 'raw_content': None}, {'title': 'UK GDP - Statistics & Facts | Statista', 'url': 'https://www.statista.com/topics/3795/gdp-of-the-uk/', 'content': 'Monthly growth of gross domestic product in the United Kingdom from January 2019 to November 2023\nContribution to GDP growth in the UK 2023, by sector\nContribution to gross domestic product growth in the United Kingdom in January 2023, by sector\nGDP growth rate in the UK 1999-2021, by country\nAnnual growth rates of gross domestic product in the United Kingdom from 1999 to 2021, by country\nGDP growth rate in the UK 2021, by region\nAnnual growth rates of gross domestic product in the United Kingdom in 2021, by region\nGDP growth of Scotland 2021, by local area\nAnnual growth rates of gross domestic product in Scotland in 2021, by local (ITL 3) area\nGDP growth of Wales 2021, by local area\nAnnual growth rates of gross domestic product in Wales in 2021, by local (ITL 3) area\nGDP growth of Northern Ireland 2021, by local area\nAnnual growth rates of gross domestic product in Northern Ireland in 2021, by local (ITL 3) area\nGDP per capita\nGDP per capita\nGDP per capita in the UK 1955-2022\nGross domestic product per capita in the United Kingdom from 1955 to 2022 (in GBP)\nAnnual GDP per capita growth in the UK 1956-2022\nAnnual GDP per capita growth in the United Kingdom from 1956 to 2022\nQuarterly GDP per capita in the UK 2019-2023\nQuarterly GDP per capita in the United Kingdom from 1st quarter 2019 to 3rd quarter 2023 (in GBP)\nQuarterly GDP per capita growth in the UK 2019-2023\nQuarterly GDP per capita growth in the United Kingdom from 1st quarter 2019 to 3rd quarter 2023 (in GBP)\nGDP per capita of the UK 1999-2021, by country\nGross domestic product per capita of the United Kingdom from 1999 to 2021, by country (in GBP)\nGDP per capita of the UK 2021, by region\nGross domestic product per capita of the United Kingdom in 2021, by region (in GBP)\nGlobal Comparisons\nGlobal Comparisons\nCountries with the largest gross domestic product (GDP) 2022\n Monthly GDP of the UK 2019-2023\nMonthly index of gross domestic product in the United Kingdom from January 2019 to November 2023 (2019=100)\nGVA of the UK 2022, by sector\nGross value added of the United Kingdom in 2022, by industry sector (in million GBP)\nGDP of the UK 2021, by country\nGross domestic product of the United Kingdom in 2021, by country (in million GBP)\nGDP of the UK 2021, by region\nGross domestic product of the United Kingdom in 2021, by region (in million GBP)\nGDP of Scotland 2021, by local area\nGross domestic product of Scotland in 2021, by local (ITL 3) area (in million GBP)\nGDP of Wales 2021, by local area\nGross domestic product of Wales in 2021, by local (ITL 3) area (in million GBP)\nGDP of Northern Ireland 2021, by local area\nGross domestic product of Northern Ireland in 2021, by local (ITL 3) area (in million GBP)\nGDP growth\nGDP growth\nGDP growth forecast for the UK 2000-2028\nForecasted annual growth of gross domestic product in the United Kingdom from 2000 to 2028\nAnnual GDP growth in the UK 1949-2022\nAnnual growth of gross domestic product in the United Kingdom from 1949 to 2022\nQuarterly GDP growth of the UK 2019-2023\nQuarterly growth of gross domestic product in the United Kingdom from 1st quarter 2019 to 3rd quarter 2023\nMonthly GDP growth of the UK 2019-2023\n Transforming data into design:\nStatista Content & Design\nStrategy and business building for the data-driven economy:\nUK GDP - Statistics & Facts\nUK economy expected to shrink in 2023\nCharacteristics of UK GDP\nKey insights\nDetailed statistics\nGDP of the UK 1948-2022\nDetailed statistics\nAnnual GDP growth in the UK 1949-2022\nDetailed statistics\nGDP per capita in the UK 1955-2022\nEditor’s Picks\nCurrent statistics on this topic\nCurrent statistics on this topic\nKey Economic Indicators\nMonthly GDP growth of the UK 2019-2023\nKey Economic Indicators\nMonthly GDP of the UK 2019-2023\nKey Economic Indicators\nContribution to GDP growth in the UK 2023, by sector\nRelated topics\nRecommended\nRecommended statistics\nGDP\nGDP\nGDP of the UK 1948-2022\nGross domestic product of the United Kingdom from 1948 to 2022 (in million GBP)\nQuarterly GDP of the UK 2019-2023\nQuarterly gross domestic product in the United Kingdom from 1st quarter 2019 to 3rd quarter 2023 (in million GBP)\n The 20 countries with the largest gross domestic product (GDP) in 2022 (in billion U.S. dollars)\nGDP of European countries in 2022\nGross domestic product at current market prices of selected European countries in 2022 (in million euros)\nReal GDP growth rates in Europe 2023\nAnnual real gross domestic product (GDP) growth rate in European countries in 2023\nGross domestic product (GDP) of Europe\'s largest economies 1980-2028\nGross domestic product (GDP) at current prices of Europe\'s largest economies from 1980 to 2028 (in billion U.S dollars)\nUnited Kingdom\'s share of global gross domestic product (GDP) 2028\nUnited Kingdom (UK): Share of global gross domestic product (GDP) adjusted for Purchasing Power Parity (PPP) from 2018 to 2028\nRelated topics\nRecommended\nReport on the topic\nKey figures\nThe most important key figures provide you with a compact summary of the topic of "UK GDP" and take you straight to the corresponding statistics.\n Industry Overview\nDigital & Trend reports\nOverview and forecasts on trending topics\nIndustry & Market reports\nIndustry and market insights and forecasts\nCompanies & Products reports\nKey figures and rankings about companies and products\nConsumer & Brand reports\nConsumer and brand insights and preferences in various industries\nPolitics & Society reports\nDetailed information about political and social topics\nCountry & Region reports\nAll key figures about countries and regions\nMarket forecast and expert KPIs for 1000+ markets in 190+ countries & territories\nInsights on consumer attitudes and behavior worldwide\nBusiness information on 100m+ public and private companies\nExplore Company Insights\nDetailed information for 39,000+ online stores and marketplaces\nDirectly accessible data for 170 industries from 150+ countries\nand over 1\xa0Mio. facts.\n', 'score': 0.97057647, 'raw_content': None}, {'title': 'GDP growth (annual %) - United Kingdom | Data - World Bank Data', 'url': 'https://data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG?locations=GB', 'content': 'GDP growth (annual %) - United Kingdom | Data - World Bank Data', 'score': 0.97052056, 'raw_content': None}, {'title': 'The UK economy - Statistics & Facts | Statista', 'url': 'https://www.statista.com/topics/6500/the-british-economy/', 'content': 'Output per hour worked in the UK 1971 to 2023\nEconomic output per hour worked in the United Kingdom from 1st quarter 1971 to 2nd quarter 2023 (2019=100)\nAnnual unemployment rate in the UK 2000-2028\nAnnual unemployment rate in the United Kingdom from 2000 to 2028\nInflation\nInflation\nInflation rate in the UK 1989-2023\nInflation rate for the Consumer Price Index (CPI) in the United Kingdom from January 1989 to October 2023\nRPI inflation rate in the UK 1948-2023\nInflation rate for the Retail Price Index (RPI) in the United Kingdom from June 1948 to October 2023\nCPIH inflation rate in the UK 1989-2023\nInflation rate for the Consumer Price Index including owner occupiers\' housing costs (CPIH) in the United Kingdom from January 1989 to October 2023\nPPI in the UK 2010-2023\nProducer Price Index (PPI) in the United Kingdom from October 2010 to October 2023\nCPI inflation rate in the UK 2023, by sector\nInflation rate for the Consumer Price Index (CPI) in the United Kingdom in October 2023, by sector\nConsumer Price Index in the UK 1988-2023\nConsumer Price Index (CPI) in the United Kingdom from 1st quarter 1988 to 3rd quarter 2023\nRetail Price Index in the UK 1987-2023\nRetail Price Index (RPI) in the United Kingdom from 1st quarter 1987 to 3rd quarter 2023\nConsumer Price Index including housing in the UK 1988-2023\nConsumer Price Index including owner occupiers\' housing costs (CPIH) in the United Kingdom from 1st quarter 1988 to 3rd quarter 2023\nRPI annual inflation rate UK 2000-2028\nAnnual inflation rate of the Retail Price Index in the United Kingdom from 2000 to 2028\nCPI annual inflation rate UK 2000-2028\nAnnual inflation rate of the Consumer Price Index in the United Kingdom from 2000 to 2028\nGovernment finances\nGovernment finances\nGovernment spending as a percentage of GDP in the UK 1900-2029\nTotal managed expenditure expressed as a percentage of GDP in the United Kingdom from 1900/01 to 2028/29\nGovernment revenue as a percentage of GDP in the UK 1900-2029\nTotal public sector current receipts expressed as a percentage of GDP in the United Kingdom from 1900/01 to 2028/29 (in million GBP)\nGovernment borrowing as a percentage of GDP in the UK 1900-2029\nPublic sector borrowing expressed as a percentage of GDP in the United Kingdom from 1900/01 to 2028/29\nNational debt as a percentage of GDP in the UK 1900-2029\nPublic sector net debt expressed as a percentage of GDP in the United Kingdom from 1900/01 to 2028/29\nPublic sector spending in the United Kingdom 2023/24\nBudgeted public sector expenditure on services in the United Kingdom in 2023/24, by function (in billion GBP)\nGovernment revenue sources in the United Kingdom 2023/24\nExpected public sector current receipts in the United Kingdom in 2023/24, by function (in billion GBP)\nBusiness Enterprise\nBusiness Enterprise\nLargest companies in the United Kingdom based on revenue 2022\nLargest companies in the United Kingdom based on revenue in 2022 (in billion US dollars)\nLargest UK companies based on number of global employees 2020\nLargest companies based in the United Kingdom on number of employees worldwide in 2020 (in 1,000s)\nNumber of private sector businesses in the UK 2000-2023\nNumber of private sector businesses in the United Kingdom from 2000 to 2023 (in millions)\nNumber of private sector businesses in the UK 2023, by sector\nNumber of private sector businesses in the United Kingdom in 2023, by sector\nNumber of businesses by enterprise size in the UK 2023\nNumber of private sector businesses in the United Kingdom in 2023, by employment size\nNumber of private sector businesses in the UK 2023, by region\nNumber of private sector businesses in the United Kingdom in 2023, by region\nNumber of local business units in the UK 2012-2023\nNumber of local units in VAT and/or PAYE based enterprises in the United Kingdom from 2012 to 2023 (in millions)\nBusiness investment index in the UK 1997-2023\nBusiness investment index in the United Kingdom from 1st quarter 1997 to 2nd quarter 2023 (Q1 1997=100)\nBusiness confidence Index in the UK 1977-2023\nBusiness confidence Index of the United Kingdom from March 1977 to November 2023 (100 = long-term average)\nRelated topics\nRecommended\nReport on the topic\nKey figures\nThe most important key figures provide you with a compact summary of the topic of "The UK economy" and take you straight to the corresponding statistics.\n Monthly GDP growth of the UK 2020-2023\nMonthly growth of gross domestic product in the United Kingdom from January 2020 to September 2023\nGDP of the UK 2021, by region\nGross domestic product of the United Kingdom in 2021, by region (in million GBP)\nGDP growth rate in the UK 2021, by region\nAnnual growth rates of gross domestic product in the United Kingdom in 2021, by region\nGDP per capita of the UK 2021, by region\nGross domestic product per capita of the United Kingdom in 2021, by region (in GBP)\nGDP growth forecast for the UK 2000-2028\nForecasted annual growth of gross domestic product in the United Kingdom from 2000 to 2028\nLabor Market\nLabor Market\nUnemployment rate of the UK 1971-2023\nUnemployment rate in the United Kingdom from March 1971 to September 2023\nEmployment rate in the UK 1971-2022\nEmployment rate in the United Kingdom from March 1971 to July 2023\nNumber of people unemployed in the UK 1971-2023\nNumber of people unemployed in the United Kingdom from March 1971 to July 2023 (in 1,000s)\nNumber of people employed in the UK 1971-2021\nNumber of people employed in the United Kingdom from March 1971 to July 2023 (in 1,000s)\nUnemployment rate in the UK 1971-2023, by gender\nUnemployment rate in the United Kingdom from 1st quarter 1971 to 2nd quarter 2023, by gender\nUnemployment rate in the UK 1992-2023, by age group\nUnemployment rate in the United Kingdom from May 1992 to July 2023, by age group\nYouth unemployment rate in the UK 1992-2023\nYouth unemployment rate in the United Kingdom from May 1992 to July 2023\nAverage annual earnings for full-time employees in the UK 1999-2023\nMedian annual earnings for full-time employees in the United Kingdom from 1999 to 2023 (in nominal GBP)\nAverage weekly earning growth in the UK 2001-2023\nAverage year-on-year growth of weekly earnings (3 month average) in the United Kingdom from March 2001 to October 2023\nNumber of redundancies in the UK 1995-2023\nAverage number of people made redundant in the United Kingdom from May 1995 to July 2023 (in 1,000s)\nOverall weekly hours worked in the UK 1971-2023\nOverall weekly hours worked for all employees in the United Kingdom from 1st quarter 1971 to 2nd quarter 2023 (in million hours worked)\n Transforming data into design:\nStatista Content & Design\nStrategy and business building for the data-driven economy:\nThe UK economy - Statistics & Facts\nUK households under pressure in 2023\nCoronavirus devastates UK economy in 2020\nKey insights\nDetailed statistics\nGDP of the UK 1948-2022\nDetailed statistics\nUnemployment rate of the UK 1971-2023\nDetailed statistics\nInflation rate in the UK 1989-2023\nEditor’s Picks\nCurrent statistics on this topic\nCurrent statistics on this topic\nWages & Salaries\nAverage weekly earning growth in the UK 2001-2023\nIncome & Expenditure\nPublic sector spending in the United Kingdom 2023/24\nEmployment\nNumber of people employed in the UK 1971-2021\nRelated topics\nRecommended\nRecommended statistics\nGross domestic product\nGross domestic product\nGDP of the UK 1948-2022\nGross domestic product of the United Kingdom from 1948 to 2022 (in million GBP)\nAnnual GDP growth in the UK 1949-2022\nAnnual growth of gross domestic product in the United Kingdom from 1949 to 2022\nGDP per capita in the UK 1955-2022\nGross domestic product per capita in the United Kingdom from 1955 to 2022 (in GBP)\nQuarterly GDP of the UK 1955-2023\nQuarterly gross domestic product in the United Kingdom from 1st quarter 1955 to 3rd quarter 2023 (in million GBP)\nQuarterly GDP growth of the UK 2015-2023\nQuarterly growth of gross domestic product in the United Kingdom from 1st quarter 2015 to 3rd quarter 2023\nQuarterly GDP per capita in the UK 1955-2023\nQuarterly GDP per capita in the United Kingdom from 1st quarter 1955 to 3rd quarter 2023 (in GBP)\nMonthly GDP of the UK 1997-2023\nMonthly index of gross domestic product in the United Kingdom from January 1997 to September 2023 (2019=100)\n GDP\nAnnual GDP growth in the UK 1949-2022\nQuarterly GDP per capita growth in the UK 2015-2023\nMonthly GDP growth of the UK 2020-2023\nGDP per capita in the UK 1955-2022\nLabor market\nNumber of people employed in the UK 1971-2021\nNumber of people unemployed in the UK 1971-2023\nDaily number of jobs furloughed in the UK 2020-2021\nAverage annual earnings for full-time employees in the UK 1999-2023\nForecasts for 2023\nGDP growth forecast for the UK 2000-2028\nAnnual unemployment rate in the UK 2000-2028\nCPI annual inflation rate UK 2000-2028\nRPI annual inflation rate UK 2000-2028\n Industry Overview\nDigital & Trend reports\nOverview and forecasts on trending topics\nIndustry & Market reports\nIndustry and market insights and forecasts\nCompanies & Products reports\nKey figures and rankings about companies and products\nConsumer & Brand reports\nConsumer and brand insights and preferences in various industries\nPolitics & Society reports\nDetailed information about political and social topics\nCountry & Region reports\nAll key figures about countries and regions\nMarket forecast and expert KPIs for 1000+ markets in 190+ countries & territories\nInsights on consumer attitudes and behavior worldwide\nBusiness information on 100m+ public and private companies\nExplore Company Insights\nDetailed information for 39,000+ online stores and marketplaces\nDirectly accessible data for 170 industries from 150+ countries\nand over 1\xa0Mio. facts.\n', 'score': 0.95998776, 'raw_content': None}, {'title': 'GDP growth (annual %) - United Kingdom | Data - World Bank Data', 'url': 'https://data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG?locations=GB&most_recent_value_desc=false', 'content': 'GDP growth (annual %) - United Kingdom | Data Data GDP growth (annual %)United Kingdom Data Catalog Data Programs International Debt Statistics Other Books and Reports For Developers GDP growth (annual %) - United Kingdom ====================================== Similar values Highest values Lowest values GDP (constant 2015 US$) GDP (current US$) GDP (constant LCU) GDP: linked series (current LCU) GDP, PPP (constant 2021 international $) GDP (current LCU) GDP, PPP (current international $) GDP per capita growth (annual %) Country Most Recent Value All Countries and Economies Country Most Recent Value This site uses cookies to optimize functionality and give you the best possible experience. If you continue to navigate this website beyond this page, cookies will be placed on your browser.', 'score': 0.7892337, 'raw_content': None}], 'response_time': 2.3}), AIMessage(content=[{'text': 'Let me search for more specific data.', 'type': 'text'}, {'id': 'toolu_019dPRXojLJoVNYFLzzSWw4w', 'input': {'query': 'UK GDP values by year 2019 2020 2021 2022 2023'}, 'name': 'tavily_search_results_json', 'type': 'tool_use'}], additional_kwargs={}, response_metadata={'id': 'msg_01Ac9vcTFneb5dvcEYXJyf1P', 'model': 'claude-3-5-sonnet-20241022', 'stop_reason': 'tool_use', 'stop_sequence': None, 'usage': {'input_tokens': 5890, 'output_tokens': 87}}, id='run-3504417f-c0b5-4908-82e2-89a18abb1b8e-0', tool_calls=[{'name': 'tavily_search_results_json', 'args': {'query': 'UK GDP values by year 2019 2020 2021 2022 2023'}, 'id': 'toolu_019dPRXojLJoVNYFLzzSWw4w', 'type': 'tool_call'}], usage_metadata={'input_tokens': 5890, 'output_tokens': 87, 'total_tokens': 5977, 'input_token_details': {}}), ToolMessage(content='[{"url": "https://www.macrotrends.net/global-metrics/countries/GBR/united-kingdom/gdp-gross-domestic-product", "content": "U.K. gdp for 2023 was $3,340.03B, a 8.13% increase from 2022. U.K. gdp for 2022 was $3,088.84B, a 1.68% decline from 2021. U.K. gdp for 2021 was $3,141.51B, a 16.45% increase from 2020. U.K. gdp for 2020 was $2,697.81B, a 5.39% decline from 2019."}, {"url": "https://countryeconomy.com/gdp/uk?year=2023", "content": "Gross Domestic Product of United Kingdom grew 0.3% in 2023 compared to last year. This rate is 45 -tenths of one percent less than the figure of 4.8% published in 2022. The GDP figure in 2023 was $3,380,855 million, leaving United Kingdom placed 6th in the ranking of GDP of the 196 countries that we publish."}, {"url": "https://www.statista.com/topics/3795/gdp-of-the-uk/", "content": "Monthly growth of gross domestic product in the United Kingdom from January 2019 to November 2023\\nContribution to GDP growth in the UK 2023, by sector\\nContribution to gross domestic product growth in the United Kingdom in January 2023, by sector\\nGDP growth rate in the UK 1999-2021, by country\\nAnnual growth rates of gross domestic product in the United Kingdom from 1999 to 2021, by country\\nGDP growth rate in the UK 2021, by region\\nAnnual growth rates of gross domestic product in the United Kingdom in 2021, by region\\nGDP growth of Scotland 2021, by local area\\nAnnual growth rates of gross domestic product in Scotland in 2021, by local (ITL 3) area\\nGDP growth of Wales 2021, by local area\\nAnnual growth rates of gross domestic product in Wales in 2021, by local (ITL 3) area\\nGDP growth of Northern Ireland 2021, by local area\\nAnnual growth rates of gross domestic product in Northern Ireland in 2021, by local (ITL 3) area\\nGDP per capita\\nGDP per capita\\nGDP per capita in the UK 1955-2022\\nGross domestic product per capita in the United Kingdom from 1955 to 2022 (in GBP)\\nAnnual GDP per capita growth in the UK 1956-2022\\nAnnual GDP per capita growth in the United Kingdom from 1956 to 2022\\nQuarterly GDP per capita in the UK 2019-2023\\nQuarterly GDP per capita in the United Kingdom from 1st quarter 2019 to 3rd quarter 2023 (in GBP)\\nQuarterly GDP per capita growth in the UK 2019-2023\\nQuarterly GDP per capita growth in the United Kingdom from 1st quarter 2019 to 3rd quarter 2023 (in GBP)\\nGDP per capita of the UK 1999-2021, by country\\nGross domestic product per capita of the United Kingdom from 1999 to 2021, by country (in GBP)\\nGDP per capita of the UK 2021, by region\\nGross domestic product per capita of the United Kingdom in 2021, by region (in GBP)\\nGlobal Comparisons\\nGlobal Comparisons\\nCountries with the largest gross domestic product (GDP) 2022\\n Monthly GDP of the UK 2019-2023\\nMonthly index of gross domestic product in the United Kingdom from January 2019 to November 2023 (2019=100)\\nGVA of the UK 2022, by sector\\nGross value added of the United Kingdom in 2022, by industry sector (in million GBP)\\nGDP of the UK 2021, by country\\nGross domestic product of the United Kingdom in 2021, by country (in million GBP)\\nGDP of the UK 2021, by region\\nGross domestic product of the United Kingdom in 2021, by region (in million GBP)\\nGDP of Scotland 2021, by local area\\nGross domestic product of Scotland in 2021, by local (ITL 3) area (in million GBP)\\nGDP of Wales 2021, by local area\\nGross domestic product of Wales in 2021, by local (ITL 3) area (in million GBP)\\nGDP of Northern Ireland 2021, by local area\\nGross domestic product of Northern Ireland in 2021, by local (ITL 3) area (in million GBP)\\nGDP growth\\nGDP growth\\nGDP growth forecast for the UK 2000-2028\\nForecasted annual growth of gross domestic product in the United Kingdom from 2000 to 2028\\nAnnual GDP growth in the UK 1949-2022\\nAnnual growth of gross domestic product in the United Kingdom from 1949 to 2022\\nQuarterly GDP growth of the UK 2019-2023\\nQuarterly growth of gross domestic product in the United Kingdom from 1st quarter 2019 to 3rd quarter 2023\\nMonthly GDP growth of the UK 2019-2023\\n Transforming data into design:\\nStatista Content & Design\\nStrategy and business building for the data-driven economy:\\nUK GDP - Statistics & Facts\\nUK economy expected to shrink in 2023\\nCharacteristics of UK GDP\\nKey insights\\nDetailed statistics\\nGDP of the UK 1948-2022\\nDetailed statistics\\nAnnual GDP growth in the UK 1949-2022\\nDetailed statistics\\nGDP per capita in the UK 1955-2022\\nEditor’s Picks\\nCurrent statistics on this topic\\nCurrent statistics on this topic\\nKey Economic Indicators\\nMonthly GDP growth of the UK 2019-2023\\nKey Economic Indicators\\nMonthly GDP of the UK 2019-2023\\nKey Economic Indicators\\nContribution to GDP growth in the UK 2023, by sector\\nRelated topics\\nRecommended\\nRecommended statistics\\nGDP\\nGDP\\nGDP of the UK 1948-2022\\nGross domestic product of the United Kingdom from 1948 to 2022 (in million GBP)\\nQuarterly GDP of the UK 2019-2023\\nQuarterly gross domestic product in the United Kingdom from 1st quarter 2019 to 3rd quarter 2023 (in million GBP)\\n The 20 countries with the largest gross domestic product (GDP) in 2022 (in billion U.S. dollars)\\nGDP of European countries in 2022\\nGross domestic product at current market prices of selected European countries in 2022 (in million euros)\\nReal GDP growth rates in Europe 2023\\nAnnual real gross domestic product (GDP) growth rate in European countries in 2023\\nGross domestic product (GDP) of Europe\'s largest economies 1980-2028\\nGross domestic product (GDP) at current prices of Europe\'s largest economies from 1980 to 2028 (in billion U.S dollars)\\nUnited Kingdom\'s share of global gross domestic product (GDP) 2028\\nUnited Kingdom (UK): Share of global gross domestic product (GDP) adjusted for Purchasing Power Parity (PPP) from 2018 to 2028\\nRelated topics\\nRecommended\\nReport on the topic\\nKey figures\\nThe most important key figures provide you with a compact summary of the topic of \\"UK GDP\\" and take you straight to the corresponding statistics.\\n Industry Overview\\nDigital & Trend reports\\nOverview and forecasts on trending topics\\nIndustry & Market reports\\nIndustry and market insights and forecasts\\nCompanies & Products reports\\nKey figures and rankings about companies and products\\nConsumer & Brand reports\\nConsumer and brand insights and preferences in various industries\\nPolitics & Society reports\\nDetailed information about political and social topics\\nCountry & Region reports\\nAll key figures about countries and regions\\nMarket forecast and expert KPIs for 1000+ markets in 190+ countries & territories\\nInsights on consumer attitudes and behavior worldwide\\nBusiness information on 100m+ public and private companies\\nExplore Company Insights\\nDetailed information for 39,000+ online stores and marketplaces\\nDirectly accessible data for 170 industries from 150+ countries\\nand over 1\xa0Mio. facts.\\n"}, {"url": "https://www.ons.gov.uk/economy/grossdomesticproductgdp/compendium/unitedkingdomnationalaccountsthebluebook/2024/nationalaccountsataglance", "content": "Real gross domestic product (GDP) is estimated to have increased by 0.3% in 2023, following a recovery from the impacts of the coronavirus (COVID-19) pandemic over the two previous years (Figure 1). Data for the UK are the Office for National Statistics (ONS) measure of real gross domestic product (GDP). Figure 9: Real GDP per head fell in 2023 when compared with 2022 in six G10 economies, including the UK Data for the UK are the Office for National Statistics (ONS) measure of real gross domestic product (GDP) per head. Download this chart Figure 9: Real GDP per head fell in 2023 when compared with 2022 in six G10 economies, including the UK"}, {"url": "https://data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG?locations=GB&most_recent_value_desc=false", "content": "GDP growth (annual %) - United Kingdom | Data Data GDP growth (annual %)United Kingdom Data Catalog Data Programs International Debt Statistics Other Books and Reports For Developers GDP growth (annual %) - United Kingdom ====================================== Similar values Highest values Lowest values GDP (constant 2015 US$) GDP (current US$) GDP (constant LCU) GDP: linked series (current LCU) GDP, PPP (constant 2021 international $) GDP (current LCU) GDP, PPP (current international $) GDP per capita growth (annual %) Country Most Recent Value All Countries and Economies Country Most Recent Value This site uses cookies to optimize functionality and give you the best possible experience. If you continue to navigate this website beyond this page, cookies will be placed on your browser."}]', name='tavily_search_results_json', id='84c571ca-27c6-4023-93a2-f0c2e8b6abb0', tool_call_id='toolu_019dPRXojLJoVNYFLzzSWw4w', artifact={'query': 'UK GDP values by year 2019 2020 2021 2022 2023', 'follow_up_questions': None, 'answer': None, 'images': [], 'results': [{'title': 'U.K. GDP 1960-2024 - Macrotrends', 'url': 'https://www.macrotrends.net/global-metrics/countries/GBR/united-kingdom/gdp-gross-domestic-product', 'content': 'U.K. gdp for 2023 was $3,340.03B, a 8.13% increase from 2022. U.K. gdp for 2022 was $3,088.84B, a 1.68% decline from 2021. U.K. gdp for 2021 was $3,141.51B, a 16.45% increase from 2020. U.K. gdp for 2020 was $2,697.81B, a 5.39% decline from 2019.', 'score': 0.9974491, 'raw_content': None}, {'title': 'United Kingdom (UK) GDP - Gross Domestic Product 2023', 'url': 'https://countryeconomy.com/gdp/uk?year=2023', 'content': 'Gross Domestic Product of United Kingdom grew 0.3% in 2023 compared to last year. This rate is 45 -tenths of one percent less than the figure of 4.8% published in 2022. The GDP figure in 2023 was $3,380,855 million, leaving United Kingdom placed 6th in the ranking of GDP of the 196 countries that we publish.', 'score': 0.9964064, 'raw_content': None}, {'title': 'UK GDP - Statistics & Facts | Statista', 'url': 'https://www.statista.com/topics/3795/gdp-of-the-uk/', 'content': 'Monthly growth of gross domestic product in the United Kingdom from January 2019 to November 2023\nContribution to GDP growth in the UK 2023, by sector\nContribution to gross domestic product growth in the United Kingdom in January 2023, by sector\nGDP growth rate in the UK 1999-2021, by country\nAnnual growth rates of gross domestic product in the United Kingdom from 1999 to 2021, by country\nGDP growth rate in the UK 2021, by region\nAnnual growth rates of gross domestic product in the United Kingdom in 2021, by region\nGDP growth of Scotland 2021, by local area\nAnnual growth rates of gross domestic product in Scotland in 2021, by local (ITL 3) area\nGDP growth of Wales 2021, by local area\nAnnual growth rates of gross domestic product in Wales in 2021, by local (ITL 3) area\nGDP growth of Northern Ireland 2021, by local area\nAnnual growth rates of gross domestic product in Northern Ireland in 2021, by local (ITL 3) area\nGDP per capita\nGDP per capita\nGDP per capita in the UK 1955-2022\nGross domestic product per capita in the United Kingdom from 1955 to 2022 (in GBP)\nAnnual GDP per capita growth in the UK 1956-2022\nAnnual GDP per capita growth in the United Kingdom from 1956 to 2022\nQuarterly GDP per capita in the UK 2019-2023\nQuarterly GDP per capita in the United Kingdom from 1st quarter 2019 to 3rd quarter 2023 (in GBP)\nQuarterly GDP per capita growth in the UK 2019-2023\nQuarterly GDP per capita growth in the United Kingdom from 1st quarter 2019 to 3rd quarter 2023 (in GBP)\nGDP per capita of the UK 1999-2021, by country\nGross domestic product per capita of the United Kingdom from 1999 to 2021, by country (in GBP)\nGDP per capita of the UK 2021, by region\nGross domestic product per capita of the United Kingdom in 2021, by region (in GBP)\nGlobal Comparisons\nGlobal Comparisons\nCountries with the largest gross domestic product (GDP) 2022\n Monthly GDP of the UK 2019-2023\nMonthly index of gross domestic product in the United Kingdom from January 2019 to November 2023 (2019=100)\nGVA of the UK 2022, by sector\nGross value added of the United Kingdom in 2022, by industry sector (in million GBP)\nGDP of the UK 2021, by country\nGross domestic product of the United Kingdom in 2021, by country (in million GBP)\nGDP of the UK 2021, by region\nGross domestic product of the United Kingdom in 2021, by region (in million GBP)\nGDP of Scotland 2021, by local area\nGross domestic product of Scotland in 2021, by local (ITL 3) area (in million GBP)\nGDP of Wales 2021, by local area\nGross domestic product of Wales in 2021, by local (ITL 3) area (in million GBP)\nGDP of Northern Ireland 2021, by local area\nGross domestic product of Northern Ireland in 2021, by local (ITL 3) area (in million GBP)\nGDP growth\nGDP growth\nGDP growth forecast for the UK 2000-2028\nForecasted annual growth of gross domestic product in the United Kingdom from 2000 to 2028\nAnnual GDP growth in the UK 1949-2022\nAnnual growth of gross domestic product in the United Kingdom from 1949 to 2022\nQuarterly GDP growth of the UK 2019-2023\nQuarterly growth of gross domestic product in the United Kingdom from 1st quarter 2019 to 3rd quarter 2023\nMonthly GDP growth of the UK 2019-2023\n Transforming data into design:\nStatista Content & Design\nStrategy and business building for the data-driven economy:\nUK GDP - Statistics & Facts\nUK economy expected to shrink in 2023\nCharacteristics of UK GDP\nKey insights\nDetailed statistics\nGDP of the UK 1948-2022\nDetailed statistics\nAnnual GDP growth in the UK 1949-2022\nDetailed statistics\nGDP per capita in the UK 1955-2022\nEditor’s Picks\nCurrent statistics on this topic\nCurrent statistics on this topic\nKey Economic Indicators\nMonthly GDP growth of the UK 2019-2023\nKey Economic Indicators\nMonthly GDP of the UK 2019-2023\nKey Economic Indicators\nContribution to GDP growth in the UK 2023, by sector\nRelated topics\nRecommended\nRecommended statistics\nGDP\nGDP\nGDP of the UK 1948-2022\nGross domestic product of the United Kingdom from 1948 to 2022 (in million GBP)\nQuarterly GDP of the UK 2019-2023\nQuarterly gross domestic product in the United Kingdom from 1st quarter 2019 to 3rd quarter 2023 (in million GBP)\n The 20 countries with the largest gross domestic product (GDP) in 2022 (in billion U.S. dollars)\nGDP of European countries in 2022\nGross domestic product at current market prices of selected European countries in 2022 (in million euros)\nReal GDP growth rates in Europe 2023\nAnnual real gross domestic product (GDP) growth rate in European countries in 2023\nGross domestic product (GDP) of Europe\'s largest economies 1980-2028\nGross domestic product (GDP) at current prices of Europe\'s largest economies from 1980 to 2028 (in billion U.S dollars)\nUnited Kingdom\'s share of global gross domestic product (GDP) 2028\nUnited Kingdom (UK): Share of global gross domestic product (GDP) adjusted for Purchasing Power Parity (PPP) from 2018 to 2028\nRelated topics\nRecommended\nReport on the topic\nKey figures\nThe most important key figures provide you with a compact summary of the topic of "UK GDP" and take you straight to the corresponding statistics.\n Industry Overview\nDigital & Trend reports\nOverview and forecasts on trending topics\nIndustry & Market reports\nIndustry and market insights and forecasts\nCompanies & Products reports\nKey figures and rankings about companies and products\nConsumer & Brand reports\nConsumer and brand insights and preferences in various industries\nPolitics & Society reports\nDetailed information about political and social topics\nCountry & Region reports\nAll key figures about countries and regions\nMarket forecast and expert KPIs for 1000+ markets in 190+ countries & territories\nInsights on consumer attitudes and behavior worldwide\nBusiness information on 100m+ public and private companies\nExplore Company Insights\nDetailed information for 39,000+ online stores and marketplaces\nDirectly accessible data for 170 industries from 150+ countries\nand over 1\xa0Mio. facts.\n', 'score': 0.97943294, 'raw_content': None}, {'title': 'National accounts at a glance - Office for National Statistics', 'url': 'https://www.ons.gov.uk/economy/grossdomesticproductgdp/compendium/unitedkingdomnationalaccountsthebluebook/2024/nationalaccountsataglance', 'content': 'Real gross domestic product (GDP) is estimated to have increased by 0.3% in 2023, following a recovery from the impacts of the coronavirus (COVID-19) pandemic over the two previous years (Figure 1). Data for the UK are the Office for National Statistics (ONS) measure of real gross domestic product (GDP). Figure 9: Real GDP per head fell in 2023 when compared with 2022 in six G10 economies, including the UK Data for the UK are the Office for National Statistics (ONS) measure of real gross domestic product (GDP) per head. Download this chart Figure 9: Real GDP per head fell in 2023 when compared with 2022 in six G10 economies, including the UK', 'score': 0.975249, 'raw_content': None}, {'title': 'GDP growth (annual %) - United Kingdom | Data - World Bank Data', 'url': 'https://data.worldbank.org/indicator/NY.GDP.MKTP.KD.ZG?locations=GB&most_recent_value_desc=false', 'content': 'GDP growth (annual %) - United Kingdom | Data Data GDP growth (annual %)United Kingdom Data Catalog Data Programs International Debt Statistics Other Books and Reports For Developers GDP growth (annual %) - United Kingdom ====================================== Similar values Highest values Lowest values GDP (constant 2015 US$) GDP (current US$) GDP (constant LCU) GDP: linked series (current LCU) GDP, PPP (constant 2021 international $) GDP (current LCU) GDP, PPP (current international $) GDP per capita growth (annual %) Country Most Recent Value All Countries and Economies Country Most Recent Value This site uses cookies to optimize functionality and give you the best possible experience. If you continue to navigate this website beyond this page, cookies will be placed on your browser.', 'score': 0.83775276, 'raw_content': None}], 'response_time': 2.37}), HumanMessage(content='Based on the search results, I can provide the UK\'s GDP values for the past 5 years (in billions of US dollars):\n\n2019: $2,851.54\n2020: $2,697.81\n2021: $3,141.51\n2022: $3,088.84\n2023: $3,340.03\n\nI\'ll pass this data to my chart generator colleague to create a line chart. They should create a line chart with:\n- Years 2019-2023 on the x-axis\n- GDP values in billions USD on the y-axis\n- Title: "UK GDP 2019-2023"\n- Clear data points showing the values\n\nOver to you, chart generator colleague!', additional_kwargs={}, response_metadata={}, name='researcher', id='7e790b7a-7b06-4b45-a595-8736b53db844')]}} ---- ``````output Python REPL can execute arbitrary code. Use with caution.

**Examples:**

Example 1 (unknown):
```unknown
pip install -U langchain_community langchain_anthropic langchain-tavily langchain_experimental matplotlib langgraph
```

Example 2 (python):
```python
import getpass
import os


def _set_if_undefined(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"Please provide your {var}")


_set_if_undefined("ANTHROPIC_API_KEY")
_set_if_undefined("TAVILY_API_KEY")
```

Example 3 (python):
```python
from typing import Annotated

from langchain_tavily import TavilySearch
from langchain_core.tools import tool
from langchain_experimental.utilities import PythonREPL

tavily_tool = TavilySearch(max_results=5)

# Warning: This executes code locally, which can be unsafe when not sandboxed

repl = PythonREPL()


@tool
def python_repl_tool(
    code: Annotated[str, "The python code to execute to generate your chart."],
):
    """Use this to execute python code. If you want to see the output of a value,
    you should print it out with `print(...)`. This is visible to the user."""
    try:
        result = repl.run(code)
    except BaseException as e:
        return f"Failed to execute. Error: {repr(e)}"
    result_str = f"Successfully executed:\n\`\`\`python\n{code}\n\`\`\`\nStdout: {result}"
    return (
        result_str + "\n\nIf you have completed all tasks, respond with FINAL ANSWER."
    )
```

Example 4 (python):
```python
def make_system_prompt(suffix: str) -> str:
    return (
        "You are a helpful AI assistant, collaborating with other assistants."
        " Use the provided tools to progress towards answering the question."
        " If you are unable to fully answer, that's OK, another assistant with different tools "
        " will help where you left off. Execute what you can to make progress."
        " If you or any of the other assistants have the final answer or deliverable,"
        " prefix your response with FINAL ANSWER so the team knows to stop."
        f"\n{suffix}"
    )
```

---

## LangGraph Swarm¶

**URL:** https://langchain-ai.github.io/langgraph/reference/swarm/

**Contents:**
- LangGraph Swarm¶
- SwarmState ¶
- create_swarm ¶
- add_active_agent_router ¶
- create_handoff_tool ¶

State schema for the multi-agent swarm.

Create a multi-agent swarm.

Add a router to the currently active agent to the StateGraph.

State schema for the multi-agent swarm.

Create a multi-agent swarm.

List of agents to add to the swarm An agent can be a LangGraph CompiledStateGraph, a functional API workflow, or any other Pregel object.

Name of the agent to route to by default (if no agents are currently active).

State schema to use for the multi-agent graph.

An optional schema for configuration. Use this to expose configurable parameters via swarm.config_specs.

A multi-agent swarm StateGraph.

Add a router to the currently active agent to the StateGraph.

The graph builder (StateGraph) to add the router to.

A list of agent (node) names to route to.

Name of the agent to route to by default (if no agents are currently active).

StateGraph with the router added.

Create a tool that can handoff control to the requested agent.

Create a tool that can handoff control to the requested agent.

The name of the agent to handoff control to, i.e. the name of the agent node in the multi-agent graph. Agent names should be simple, clear and unique, preferably in snake_case, although you are only limited to the names accepted by LangGraph nodes as well as the tool names accepted by LLM providers (the tool name will look like this: transfer_to_<agent_name>).

Optional name of the tool to use for the handoff. If not provided, the tool name will be transfer_to_<agent_name>.

Optional description for the handoff tool. If not provided, the tool description will be Ask agent <agent_name> for help.

**Examples:**

Example 1 (unknown):
```unknown
create_swarm(
    agents: list[Pregel],
    *,
    default_active_agent: str,
    state_schema: StateSchemaType = SwarmState,
    config_schema: type[Any] | None = None
) -> StateGraph
```

Example 2 (python):
```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from langgraph_swarm import create_handoff_tool, create_swarm

def add(a: int, b: int) -> int:
    '''Add two numbers'''
    return a + b

alice = create_react_agent(
    "openai:gpt-4o",
    [add, create_handoff_tool(agent_name="Bob")],
    prompt="You are Alice, an addition expert.",
    name="Alice",
)

bob = create_react_agent(
    "openai:gpt-4o",
    [create_handoff_tool(agent_name="Alice", description="Transfer to Alice, she can help with math")],
    prompt="You are Bob, you speak like a pirate.",
    name="Bob",
)

checkpointer = InMemorySaver()
workflow = create_swarm(
    [alice, bob],
    default_active_agent="Alice"
)
app = workflow.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "1"}}
turn_1 = app.invoke(
    {"messages": [{"role": "user", "content": "i'd like to speak to Bob"}]},
    config,
)
turn_2 = app.invoke(
    {"messages": [{"role": "user", "content": "what's 5 + 7?"}]},
    config,
)
```

Example 3 (unknown):
```unknown
add_active_agent_router(
    builder: StateGraph,
    *,
    route_to: list[str],
    default_active_agent: str
) -> StateGraph
```

Example 4 (python):
```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph
from langgraph_swarm import SwarmState, create_handoff_tool, add_active_agent_router

def add(a: int, b: int) -> int:
    '''Add two numbers'''
    return a + b

alice = create_react_agent(
    "openai:gpt-4o",
    [add, create_handoff_tool(agent_name="Bob")],
    prompt="You are Alice, an addition expert.",
    name="Alice",
)

bob = create_react_agent(
    "openai:gpt-4o",
    [create_handoff_tool(agent_name="Alice", description="Transfer to Alice, she can help with math")],
    prompt="You are Bob, you speak like a pirate.",
    name="Bob",
)

checkpointer = InMemorySaver()
workflow = (
    StateGraph(SwarmState)
    .add_node(alice, destinations=("Bob",))
    .add_node(bob, destinations=("Alice",))
)
# this is the router that enables us to keep track of the last active agent
workflow = add_active_agent_router(
    builder=workflow,
    route_to=["Alice", "Bob"],
    default_active_agent="Alice",
)

# compile the workflow
app = workflow.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "1"}}
turn_1 = app.invoke(
    {"messages": [{"role": "user", "content": "i'd like to speak to Bob"}]},
    config,
)
turn_2 = app.invoke(
    {"messages": [{"role": "user", "content": "what's 5 + 7?"}]},
    config,
)
```

---

## Hierarchical Agent Teams¶

**URL:** https://langchain-ai.github.io/langgraph/tutorials/multi_agent/hierarchical_agent_teams/

**Contents:**
- Hierarchical Agent Teams¶
- Setup¶
- Create Tools¶
- Helper Utilities¶
- Define Agent Teams¶
  - Research Team¶
  - Document Writing Team¶
- Add Layers¶

In our previous example (Agent Supervisor), we introduced the concept of a single supervisor node to route work between different worker nodes.

But what if the job for a single worker becomes too complex? What if the number of workers becomes too large?

For some applications, the system may be more effective if work is distributed hierarchically.

You can do this by composing different subgraphs and creating a top-level supervisor, along with mid-level supervisors.

To do this, let's build a simple research assistant! The graph will look something like the following:

This notebook is inspired by the paper AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation, by Wu, et. al. In the rest of this notebook, you will:

First, let's install our required packages and set our API keys

Set up LangSmith for LangGraph development

Sign up for LangSmith to quickly spot issues and improve the performance of your LangGraph projects. LangSmith lets you use trace data to debug, test, and monitor your LLM apps built with LangGraph — read more about how to get started here.

Each team will be composed of one or more agents each with one or more tools. Below, define all the tools to be used by your different teams.

We'll start with the research team.

The research team can use a search engine and url scraper to find information on the web. Feel free to add additional functionality below to boost the team performance!

API Reference: WebBaseLoader | TavilySearch | tool

Document writing team tools

Next up, we will give some tools for the doc writing team to use. We define some bare-bones file-access tools below.

Note that this gives the agents access to your file-system, which can be unsafe. We also haven't optimized the tool descriptions for performance.

API Reference: PythonREPL

We are going to create a few utility functions to make it more concise when we want to:

These will simplify the graph compositional code at the end for us so it's easier to see what's going on.

API Reference: BaseChatModel | StateGraph | START | END | Command | HumanMessage | trim_messages

Now we can get to define our hierarchical teams. "Choose your player!"

The research team will have a search agent and a web scraping "research_agent" as the two worker nodes. Let's create those, as well as the team supervisor.

API Reference: HumanMessage | ChatOpenAI | create_react_agent

Now that we've created the necessary components, defining their interactions is easy. Add the nodes to the team graph, and define the edges, which determine the transition criteria.

We can give this team work directly. Try it out below.

for s in research_graph.stream( {"messages": [("user", "when is Taylor Swift's next tour?")]}, {"recursion_limit": 100}, ): print(s) print("---") {'supervisor': {'next': 'search'}} --- {'search': {'messages': [HumanMessage(content="Taylor Swift's next tour is The Eras Tour, which includes both U.S. and international dates. She announced additional U.S. dates for 2024. You can find more details about the tour and ticket information on platforms like Ticketmaster and official announcements.", additional_kwargs={}, response_metadata={}, name='search', id='4df8687b-50a8-4342-aad5-680732c4a10f')]}} --- {'supervisor': {'next': 'web_scraper'}} --- {'web_scraper': {'messages': [HumanMessage(content='Taylor Swift\'s next tour is "The Eras Tour." Here are some of the upcoming international dates for 2024 that were listed on Ticketmaster:\n\n1. **Toronto, ON, Canada** at Rogers Centre\n - November 21, 2024\n - November 22, 2024\n - November 23, 2024\n\n2. **Vancouver, BC, Canada** at BC Place\n - December 6, 2024\n - December 7, 2024\n - December 8, 2024\n\nFor the most current information and additional dates, you can check platforms like Ticketmaster or Taylor Swift\'s [official website](https://www.taylorswift.com/events).', additional_kwargs={}, response_metadata={}, name='web_scraper', id='27524ebc-d179-4733-831d-ee10a58a2528')]}} --- {'supervisor': {'next': '__end__'}} ---

Create the document writing team below using a similar approach. This time, we will give each agent access to different file-writing tools.

Note that we are giving file-system access to our agent here, which is not safe in all cases.

With the objects themselves created, we can form the graph.

for s in paper_writing_graph.stream( { "messages": [ ( "user", "Write an outline for poem about cats and then write the poem to disk.", ) ] }, {"recursion_limit": 100}, ): print(s) print("---") {'supervisor': {'next': 'note_taker'}} --- {'note_taker': {'messages': [HumanMessage(content='The outline for the poem about cats has been created and saved as "cats_poem_outline.txt".', additional_kwargs={}, response_metadata={}, name='note_taker', id='14a5d8ca-9092-416f-96ee-ba16686e8658')]}} --- {'supervisor': {'next': 'doc_writer'}} --- {'doc_writer': {'messages': [HumanMessage(content='The poem about cats has been written and saved as "cats_poem.txt".', additional_kwargs={}, response_metadata={}, name='doc_writer', id='c4e31a94-63ae-4632-9e80-1166f3f138b2')]}} --- {'supervisor': {'next': '__end__'}} ---

In this design, we are enforcing a top-down planning policy. We've created two graphs already, but we have to decide how to route work between the two.

We'll create a third graph to orchestrate the previous two, and add some connectors to define how this top-level state is shared between the different graphs.

API Reference: BaseMessage

for s in super_graph.stream( { "messages": [ ("user", "Research AI agents and write a brief report about them.") ], }, {"recursion_limit": 150}, ): print(s) print("---") {'supervisor': {'next': 'research_team'}} --- {'research_team': {'messages': [HumanMessage(content="**AI Agents Overview 2023**\n\nAI agents are sophisticated technologies that automate and enhance various processes across industries, becoming increasingly integral to business operations. In 2023, these agents are notable for their advanced capabilities in communication, data visualization, and language processing.\n\n**Popular AI Agents in 2023:**\n1. **Auto GPT**: This agent is renowned for its seamless integration abilities, significantly impacting industries by improving communication and operational workflows.\n2. **ChartGPT**: Specializing in data visualization, ChartGPT enables users to interact with data innovatively, providing deeper insights and comprehension.\n3. **LLMops**: With advanced language capabilities, LLMops is a versatile tool seeing widespread use across multiple sectors.\n\n**Market Trends:**\nThe AI agents market is experiencing rapid growth, with significant advancements anticipated by 2030. There's a growing demand for AI agents in personalized interactions, particularly within customer service, healthcare, and marketing sectors. This trend is fueled by the need for more efficient and tailored customer experiences.\n\n**Key Players:**\nLeading companies such as Microsoft, IBM, Google, Oracle, and AWS are key players in the AI agents market, highlighting the widespread adoption and investment in these technologies.\n\n**Technological Innovations:**\nAI agents are being developed alongside simulation technologies for robust testing and deployment environments. Innovations in generative AI are accelerating, supported by advancements in large language models and platforms like ChatGPT.\n\n**Applications in Healthcare:**\nIn healthcare, AI agents are automating routine tasks, allowing medical professionals to focus more on patient care. They're poised to significantly enhance healthcare delivery and efficiency.\n\n**Future Prospects:**\nThe future of AI agents is promising, with continued evolution and integration into various platforms and ecosystems, offering more seamless and intelligent interactions. As these technologies advance, they are expected to redefine business operations and customer interactions.", additional_kwargs={}, response_metadata={}, name='research_team', id='5f6606e0-838c-406c-b50d-9f9f6a076322')]}} --- {'supervisor': {'next': 'writing_team'}} --- {'writing_team': {'messages': [HumanMessage(content="Here are the contents of the documents:\n\n### AI Agents Overview 2023\n\n**AI Agents Overview 2023**\n\nAI agents are sophisticated technologies that automate and enhance various processes across industries, becoming increasingly integral to business operations. In 2023, these agents are notable for their advanced capabilities in communication, data visualization, and language processing.\n\n**Popular AI Agents in 2023:**\n1. **Auto GPT**: This agent is renowned for its seamless integration abilities, significantly impacting industries by improving communication and operational workflows.\n2. **ChartGPT**: Specializing in data visualization, ChartGPT enables users to interact with data innovatively, providing deeper insights and comprehension.\n3. **LLMops**: With advanced language capabilities, LLMops is a versatile tool seeing widespread use across multiple sectors.\n\n**Market Trends:**\nThe AI agents market is experiencing rapid growth, with significant advancements anticipated by 2030. There's a growing demand for AI agents in personalized interactions, particularly within customer service, healthcare, and marketing sectors. This trend is fueled by the need for more efficient and tailored customer experiences.\n\n**Key Players:**\nLeading companies such as Microsoft, IBM, Google, Oracle, and AWS are key players in the AI agents market, highlighting the widespread adoption and investment in these technologies.\n\n**Technological Innovations:**\nAI agents are being developed alongside simulation technologies for robust testing and deployment environments. Innovations in generative AI are accelerating, supported by advancements in large language models and platforms like ChatGPT.\n\n**Applications in Healthcare:**\nIn healthcare, AI agents are automating routine tasks, allowing medical professionals to focus more on patient care. They're poised to significantly enhance healthcare delivery and efficiency.\n\n**Future Prospects:**\nThe future of AI agents is promising, with continued evolution and integration into various platforms and ecosystems, offering more seamless and intelligent interactions. As these technologies advance, they are expected to redefine business operations and customer interactions.\n\n### AI_Agents_Overview_2023_Outline\n\n1. Introduction to AI Agents in 2023\n2. Popular AI Agents: Auto GPT, ChartGPT, LLMops\n3. Market Trends and Growth\n4. Key Players in the AI Agents Market\n5. Technological Innovations: Simulation and Generative AI\n6. Applications of AI Agents in Healthcare\n7. Future Prospects of AI Agents", additional_kwargs={}, response_metadata={}, name='writing_team', id='851bd8a6-740e-488c-8928-1f9e05e96ea0')]}} --- {'supervisor': {'next': 'writing_team'}} --- {'writing_team': {'messages': [HumanMessage(content='The documents have been successfully created and saved:\n\n1. **AI_Agents_Overview_2023.txt** - Contains the detailed overview of AI agents in 2023.\n2. **AI_Agents_Overview_2023_Outline.txt** - Contains the outline of the document.', additional_kwargs={}, response_metadata={}, name='writing_team', id='c87c0778-a085-4a8e-8ee1-9b43b9b0b143')]}} --- {'supervisor': {'next': '__end__'}} ---

**Examples:**

Example 1 (unknown):
```unknown
pip install -U langgraph langchain_community langchain_anthropic langchain-tavily langchain_experimental
```

Example 2 (python):
```python
import getpass
import os


def _set_if_undefined(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"Please provide your {var}")


_set_if_undefined("OPENAI_API_KEY")
_set_if_undefined("TAVILY_API_KEY")
```

Example 3 (python):
```python
from typing import Annotated, List

from langchain_community.document_loaders import WebBaseLoader
from langchain_tavily import TavilySearch
from langchain_core.tools import tool

tavily_tool = TavilySearch(max_results=5)


@tool
def scrape_webpages(urls: List[str]) -> str:
    """Use requests and bs4 to scrape the provided web pages for detailed information."""
    loader = WebBaseLoader(urls)
    docs = loader.load()
    return "\n\n".join(
        [
            f'<Document name="{doc.metadata.get("title", "")}">\n{doc.page_content}\n</Document>'
            for doc in docs
        ]
    )
```

Example 4 (python):
```python
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Optional

from langchain_experimental.utilities import PythonREPL
from typing_extensions import TypedDict

_TEMP_DIRECTORY = TemporaryDirectory()
WORKING_DIRECTORY = Path(_TEMP_DIRECTORY.name)


@tool
def create_outline(
    points: Annotated[List[str], "List of main points or sections."],
    file_name: Annotated[str, "File path to save the outline."],
) -> Annotated[str, "Path of the saved outline file."]:
    """Create and save an outline."""
    with (WORKING_DIRECTORY / file_name).open("w") as file:
        for i, point in enumerate(points):
            file.write(f"{i + 1}. {point}\n")
    return f"Outline saved to {file_name}"


@tool
def read_document(
    file_name: Annotated[str, "File path to read the document from."],
    start: Annotated[Optional[int], "The start line. Default is 0"] = None,
    end: Annotated[Optional[int], "The end line. Default is None"] = None,
) -> str:
    """Read the specified document."""
    with (WORKING_DIRECTORY / file_name).open("r") as file:
        lines = file.readlines()
    if start is None:
        start = 0
    return "\n".join(lines[start:end])


@tool
def write_document(
    content: Annotated[str, "Text content to be written into the document."],
    file_name: Annotated[str, "File path to save the document."],
) -> Annotated[str, "Path of the saved document file."]:
    """Create and save a text document."""
    with (WORKING_DIRECTORY / file_name).open("w") as file:
        file.write(content)
    return f"Document saved to {file_name}"


@tool
def edit_document(
    file_name: Annotated[str, "Path of the document to be edited."],
    inserts: Annotated[
        Dict[int, str],
        "Dictionary where key is the line number (1-indexed) and value is the text to be inserted at that line.",
    ],
) -> Annotated[str, "Path of the edited document file."]:
    """Edit a document by inserting text at specific line numbers."""

    with (WORKING_DIRECTORY / file_name).open("r") as file:
        lines = file.readlines()

    sorted_inserts = sorted(inserts.items())

    for line_number, text in sorted_inserts:
        if 1 <= line_number <= len(lines) + 1:
            lines.insert(line_number - 1, text + "\n")
        else:
            return f"Error: Line number {line_number} is out of range."

    with (WORKING_DIRECTORY / file_name).open("w") as file:
        file.writelines(lines)

    return f"Document edited and saved to {file_name}"


# Warning: This executes code locally, which can be unsafe when not sandboxed

repl = PythonREPL()


@tool
def python_repl_tool(
    code: Annotated[str, "The python code to execute to generate your chart."],
):
    """Use this to execute python code. If you want to see the output of a value,
    you should print it out with `print(...)`. This is visible to the user."""
    try:
        result = repl.run(code)
    except BaseException as e:
        return f"Failed to execute. Error: {repr(e)}"
    return f"Successfully executed:\n\`\`\`python\n{code}\n\`\`\`\nStdout: {result}"
```

---

## Local RAG agent with LLaMA3¶

**URL:** https://langchain-ai.github.io/langgraph/tutorials/rag/langgraph_adaptive_rag_local/

**Contents:**
- Local RAG agent with LLaMA3¶
- Local models¶
  - Embedding¶
  - LLM¶
  - Search¶
  - Tracing¶
  - Vectorstore¶
  - Components¶
- Web Search Tool¶
- Graph¶

We'll combine ideas from paper RAG papers into a RAG agent:

Use Ollama and llama3.2:

API Reference: ChatOllama

For search, we use Tavily, which is a search engine optimized for LLMs and RAG.

Optionally, use LangSmith for tracing.

API Reference: RecursiveCharacterTextSplitter | WebBaseLoader | SKLearnVectorStore | NomicEmbeddings

from langchain.text_splitter import RecursiveCharacterTextSplitter from langchain_community.document_loaders import WebBaseLoader from langchain_community.vectorstores import SKLearnVectorStore from langchain_nomic.embeddings import NomicEmbeddings urls = [ "https://lilianweng.github.io/posts/2023-06-23-agent/", "https://lilianweng.github.io/posts/2023-03-15-prompt-engineering/", "https://lilianweng.github.io/posts/2023-10-25-adv-attack-llm/", ] # Load documents docs = [WebBaseLoader(url).load() for url in urls] docs_list = [item for sublist in docs for item in sublist] # Split documents text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder( chunk_size=1000, chunk_overlap=200 ) doc_splits = text_splitter.split_documents(docs_list) # Add to vectorDB vectorstore = SKLearnVectorStore.from_documents( documents=doc_splits, embedding=NomicEmbeddings(model="nomic-embed-text-v1.5", inference_mode="local"), ) # Create retriever retriever = vectorstore.as_retriever(k=3) USER_AGENT environment variable not set, consider setting it to identify your requests.

API Reference: HumanMessage | SystemMessage

### Router import json from langchain_core.messages import HumanMessage, SystemMessage # Prompt router_instructions = """You are an expert at routing a user question to a vectorstore or web search. The vectorstore contains documents related to agents, prompt engineering, and adversarial attacks. Use the vectorstore for questions on these topics. For all else, and especially for current events, use web-search. Return JSON with single key, datasource, that is 'websearch' or 'vectorstore' depending on the question.""" # Test router test_web_search = llm_json_mode.invoke( [SystemMessage(content=router_instructions)] + [ HumanMessage( content="Who is favored to win the NFC Championship game in the 2024 season?" ) ] ) test_web_search_2 = llm_json_mode.invoke( [SystemMessage(content=router_instructions)] + [HumanMessage(content="What are the models released today for llama3.2?")] ) test_vector_store = llm_json_mode.invoke( [SystemMessage(content=router_instructions)] + [HumanMessage(content="What are the types of agent memory?")] ) print( json.loads(test_web_search.content), json.loads(test_web_search_2.content), json.loads(test_vector_store.content), ) {'datasource': 'websearch'} {'datasource': 'websearch'} {'datasource': 'vectorstore'}

### Generate # Prompt rag_prompt = """You are an assistant for question-answering tasks. Here is the context to use to answer the question: {context} Think carefully about the above context. Now, review the user question: {question} Provide an answer to this questions using only the above context. Use three sentences maximum and keep the answer concise. Answer:""" # Post-processing def format_docs(docs): return "\n\n".join(doc.page_content for doc in docs) # Test docs = retriever.invoke(question) docs_txt = format_docs(docs) rag_prompt_formatted = rag_prompt.format(context=docs_txt, question=question) generation = llm.invoke([HumanMessage(content=rag_prompt_formatted)]) print(generation.content) Chain of Thought (CoT) prompting is a technique used in natural language processing to generate human-like responses by iteratively asking questions and refining the search space through external search queries, such as Wikipedia APIs. CoT prompting involves decomposing problems into multiple thought steps, generating multiple thoughts per step, and evaluating each state using a classifier or majority vote. The goal is to find an optimal instruction that leads to the desired output, which can be achieved by optimizing prompt parameters directly on the embedding space via gradient descent or searching over a pool of model-generated instruction candidates.

API Reference: TavilySearchResults

We build the above workflow as a graph using LangGraph.

The graph state schema contains keys that we want to:

See conceptual docs here.

Each node in our graph is simply a function that:

(1) Take state as an input

(3) Write the modified state to the state schema (dict)

See conceptual docs here.

Each edge routes between nodes in the graph.

See conceptual docs here.

API Reference: Document | END

API Reference: StateGraph

https://smith.langchain.com/public/1e01baea-53e9-4341-a6d1-b1614a800a97/r

https://smith.langchain.com/public/acdfa49d-aa11-48fb-9d9c-13a687ff311f/r

**Examples:**

Example 1 (unknown):
```unknown
pip install --quiet -U langchain langchain_community tiktoken langchain-nomic "nomic[local]" langchain-ollama scikit-learn langgraph tavily-python bs4
```

Example 2 (unknown):
```unknown
pip install langchain-nomic
```

Example 3 (unknown):
```unknown
ollama pull llama3.2:3b-instruct-fp16
```

Example 4 (python):
```python
### LLM
from langchain_ollama import ChatOllama

local_llm = "llama3.2:3b-instruct-fp16"
llm = ChatOllama(model=local_llm, temperature=0)
llm_json_mode = ChatOllama(model=local_llm, temperature=0, format="json")
```

---

## Agents¶

**URL:** https://langchain-ai.github.io/langgraph/reference/agents/

**Contents:**
- Agents¶
- AgentState ¶
- create_react_agent ¶
- ToolNode ¶
  - inject_tool_args ¶
- InjectedState ¶
  - __init__ ¶
- InjectedStore ¶
- tools_condition ¶
- ValidationNode ¶

The state of the agent.

Creates an agent graph that calls tools in a loop until a stopping condition is met.

The state of the agent.

Creates an agent graph that calls tools in a loop until a stopping condition is met.

For more details on using create_react_agent, visit Agents documentation.

The language model for the agent. Supports static and dynamic model selection.

Dynamic functions receive graph state and runtime, enabling context-dependent model selection. Must return a BaseChatModel instance. For tool calling, bind tools using .bind_tools(). Bound tools must be a subset of the tools parameter.

Dynamic model example: from dataclasses import dataclass @dataclass class ModelContext: model_name: str = "gpt-3.5-turbo" # Instantiate models globally gpt4_model = ChatOpenAI(model="gpt-4") gpt35_model = ChatOpenAI(model="gpt-3.5-turbo") def select_model(state: AgentState, runtime: Runtime[ModelContext]) -> ChatOpenAI: model_name = runtime.context.model_name model = gpt4_model if model_name == "gpt-4" else gpt35_model return model.bind_tools(tools)

Dynamic Model Requirements

Ensure returned models have appropriate tools bound via .bind_tools() and support required functionality. Bound tools must be a subset of those specified in the tools parameter.

A list of tools or a ToolNode instance. If an empty list is provided, the agent will consist of a single LLM node without tool calling.

An optional prompt for the LLM. Can take a few different forms:

An optional schema for the final agent output.

If provided, output will be formatted to match the given schema and returned in the 'structured_response' state key. If not provided, structured_response will not be present in the output state. Can be passed in as:

response_format requires the model to support .with_structured_output

The graph will make a separate call to the LLM to generate the structured response after the agent loop is finished. This is not the only strategy to get structured responses, see more options in this guide.

An optional node to add before the agent node (i.e., the node that calls the LLM). Useful for managing long message histories (e.g., message trimming, summarization, etc.). Pre-model hook must be a callable or a runnable that takes in current graph state and returns a state update in the form of # At least one of `messages` or `llm_input_messages` MUST be provided { # If provided, will UPDATE the `messages` in the state "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), ...], # If provided, will be used as the input to the LLM, # and will NOT UPDATE `messages` in the state "llm_input_messages": [...], # Any other state keys that need to be propagated ... }

At least one of messages or llm_input_messages MUST be provided and will be used as an input to the agent node. The rest of the keys will be added to the graph state.

If you are returning messages in the pre-model hook, you should OVERWRITE the messages key by doing the following:

An optional node to add after the agent node (i.e., the node that calls the LLM). Useful for implementing human-in-the-loop, guardrails, validation, or other post-processing. Post-model hook must be a callable or a runnable that takes in current graph state and returns a state update.

Only available with version="v2".

An optional state schema that defines graph state. Must have messages and remaining_steps keys. Defaults to AgentState that defines those two keys.

remaining_steps is used to limit the number of steps the react agent can take. Calculated roughly as recursion_limit - total_steps_taken. If remaining_steps is less than 2 and tool calls are present in the response, the react agent will return a final AI Message with the content "Sorry, need more steps to process this request.". No GraphRecusionError will be raised in this case.

An optional schema for runtime context.

An optional checkpoint saver object. This is used for persisting the state of the graph (e.g., as chat memory) for a single thread (e.g., a single conversation).

An optional store object. This is used for persisting data across multiple threads (e.g., multiple conversations / users).

An optional list of node names to interrupt before. Should be one of the following: "agent", "tools". This is useful if you want to add a user confirmation or other interrupt before taking an action.

An optional list of node names to interrupt after. Should be one of the following: "agent", "tools". This is useful if you want to return directly or run additional processing on an output.

A flag indicating whether to enable debug mode.

Determines the version of the graph to create. Can be one of:

An optional name for the CompiledStateGraph. This name will be automatically used when adding ReAct agent graph to another graph as a subgraph node - particularly useful for building multi-agent systems.

config_schema Deprecated

The config_schema parameter is deprecated in v0.6.0 and support will be removed in v2.0.0. Please use context_schema instead to specify the schema for run-scoped context.

A compiled LangChain runnable that can be used for chat interactions.

The "agent" node calls the language model with the messages list (after applying the prompt). If the resulting AIMessage contains tool_calls, the graph will then call the "tools". The "tools" node executes the tools (1 tool per tool_call) and adds the responses to the messages list as ToolMessage objects. The agent node then calls the language model again. The process repeats until no more tool_calls are present in the response. The agent then returns the full list of messages as a dictionary containing the key "messages".

Bases: RunnableCallable

A node that runs the tools called in the last AIMessage.

It can be used either in StateGraph with a "messages" state key (or a custom key passed via ToolNode's 'messages_key'). If multiple tool calls are requested, they will be run in parallel. The output will be a list of ToolMessages, one for each tool call.

Tool calls can also be passed directly as a list of ToolCall dicts.

Basic usage with simple tools:

Custom error handling:

Direct tool call execution:

The ToolNode expects input in one of three formats: 1. A dictionary with a messages key containing a list of messages 2. A list of messages directly 3. A list of tool call dictionaries

When using message formats, the last message must be an AIMessage with tool_calls populated. The node automatically extracts and processes these tool calls concurrently.

For advanced use cases involving state injection or store access, tools can be annotated with InjectedState or InjectedStore to receive graph context automatically.

Inject graph state and store into tool call arguments.

Inject graph state and store into tool call arguments.

This method enables tools to access graph context that should not be controlled by the model. Tools can declare dependencies on graph state or persistent storage using InjectedState and InjectedStore annotations. This method automatically identifies these dependencies and injects the appropriate values.

The injection process preserves the original tool call structure while adding the necessary context arguments. This allows tools to be both model-callable and context-aware without exposing internal state management to the model.

The tool call dictionary to augment with injected arguments. Must contain 'name', 'args', 'id', and 'type' fields.

The current graph state to inject into tools requiring state access. Can be a message list, state dictionary, or BaseModel instance.

The persistent store instance to inject into tools requiring storage. Will be None if no store is configured for the graph.

A new ToolCall dictionary with the same structure as the input but with

additional arguments injected based on the tool's annotation requirements.

If a tool requires store injection but no store is provided, or if state injection requirements cannot be satisfied.

This method is automatically called during tool execution but can also be used manually when working with the Send API or custom routing logic. The injection is performed on a copy of the tool call to avoid mutating the original.

Tool execution node for LangGraph workflows.

This module provides prebuilt functionality for executing tools in LangGraph.

Tools are functions that models can call to interact with external systems, APIs, databases, or perform computations.

The module implements several key design patterns: - Parallel execution of multiple tool calls for efficiency - Robust error handling with customizable error messages - State injection for tools that need access to graph state - Store injection for tools that need persistent storage - Command-based state updates for advanced control flow

ToolNode: Main class for executing tools in LangGraph workflows InjectedState: Annotation for injecting graph state into tools InjectedStore: Annotation for injecting persistent store into tools tools_condition: Utility function for conditional routing based on tool calls

Annotation for injecting graph state into tool arguments.

Annotation for injecting persistent store into tool arguments.

Conditional routing function for tool-calling workflows.

Bases: InjectedToolArg

Annotation for injecting graph state into tool arguments.

This annotation enables tools to access graph state without exposing state management details to the language model. Tools annotated with InjectedState receive state data automatically during execution while remaining invisible to the model's tool-calling interface.

Initialize InjectedState annotation.

Initialize InjectedState annotation.

Optional key to extract from the state dictionary. If None, the entire state is injected. If specified, only that field's value is injected. This allows tools to request specific state components rather than processing the full state structure.

Bases: InjectedToolArg

Annotation for injecting persistent store into tool arguments.

This annotation enables tools to access LangGraph's persistent storage system without exposing storage details to the language model. Tools annotated with InjectedStore receive the store instance automatically during execution while remaining invisible to the model's tool-calling interface.

The store provides persistent, cross-session data storage that tools can use for maintaining context, user preferences, or any other data that needs to persist beyond individual workflow executions.

InjectedStore annotation requires langchain-core >= 0.3.8

Usage with ToolNode and graph compilation:

Cross-session persistence:

Conditional routing function for tool-calling workflows.

This utility function implements the standard conditional logic for ReAct-style agents: if the last AI message contains tool calls, route to the tool execution node; otherwise, end the workflow. This pattern is fundamental to most tool-calling agent architectures.

The function handles multiple state formats commonly used in LangGraph applications, making it flexible for different graph designs while maintaining consistent behavior.

The current graph state to examine for tool calls. Supported formats: - Dictionary containing a messages key (for StateGraph) - BaseModel instance with a messages attribute

The key or attribute name containing the message list in the state. This allows customization for graphs using different state schemas. Defaults to "messages".

Either "tools" if tool calls are present in the last AI message, or "end"

to terminate the workflow. These are the standard routing destinations for

tool-calling conditional edges.

If no messages can be found in the provided state format.

Basic usage in a ReAct agent:

This function is designed to work seamlessly with ToolNode and standard LangGraph patterns. It expects the last message to be an AIMessage when tool calls are present, which is the standard output format for tool-calling language models.

Bases: RunnableCallable

A node that validates all tools requests from the last AIMessage.

It can be used either in StateGraph with a "messages" key.

This node does not actually run the tools, it only validates the tool calls, which is useful for extraction and other use cases where you need to generate structured output that conforms to a complex schema without losing the original messages and tool IDs (for use in multi-turn conversations).

A list of ToolMessages with the validated content or error messages.

Configuration that defines what actions are allowed for a human interrupt.

Represents a request for human action within the graph execution.

Represents an interrupt triggered by the graph that requires human intervention.

The response provided by a human to an interrupt, which is returned when graph execution resumes.

Configuration that defines what actions are allowed for a human interrupt.

This controls the available interaction options when the graph is paused for human input.

Whether the human can choose to ignore/skip the current step

Whether the human can provide a text response/feedback

Whether the human can edit the provided content/state

Whether the human can accept/approve the current state

Represents a request for human action within the graph execution.

Contains the action type and any associated arguments needed for the action.

The type or name of action being requested (e.g., "Approve XYZ action")

Key-value pairs of arguments needed for the action

Represents an interrupt triggered by the graph that requires human intervention.

This is passed to the interrupt function when execution is paused for human input.

The specific action being requested from the human

Configuration defining what actions are allowed

Optional detailed description of what input is needed

The response provided by a human to an interrupt, which is returned when graph execution resumes.

The type of response: - "accept": Approves the current state without changes - "ignore": Skips/ignores the current step - "response": Provides text feedback or instructions - "edit": Modifies the current state/content

The response payload: - None: For ignore/accept actions - str: For text responses - ActionRequest: For edit actions with updated content

**Examples:**

Example 1 (unknown):
```unknown
create_react_agent(
    model: (
        str
        | LanguageModelLike
        | Callable[
            [StateSchema, Runtime[ContextT]], BaseChatModel
        ]
        | Callable[
            [StateSchema, Runtime[ContextT]],
            Awaitable[BaseChatModel],
        ]
        | Callable[
            [StateSchema, Runtime[ContextT]],
            Runnable[LanguageModelInput, BaseMessage],
        ]
        | Callable[
            [StateSchema, Runtime[ContextT]],
            Awaitable[
                Runnable[LanguageModelInput, BaseMessage]
            ],
        ]
    ),
    tools: (
        Sequence[BaseTool | Callable | dict[str, Any]]
        | ToolNode
    ),
    *,
    prompt: Prompt | None = None,
    response_format: (
        StructuredResponseSchema
        | tuple[str, StructuredResponseSchema]
        | None
    ) = None,
    pre_model_hook: RunnableLike | None = None,
    post_model_hook: RunnableLike | None = None,
    state_schema: StateSchemaType | None = None,
    context_schema: type[Any] | None = None,
    checkpointer: Checkpointer | None = None,
    store: BaseStore | None = None,
    interrupt_before: list[str] | None = None,
    interrupt_after: list[str] | None = None,
    debug: bool = False,
    version: Literal["v1", "v2"] = "v2",
    name: str | None = None,
    **deprecated_kwargs: Any
) -> CompiledStateGraph
```

Example 2 (python):
```python
from dataclasses import dataclass

@dataclass
class ModelContext:
    model_name: str = "gpt-3.5-turbo"

# Instantiate models globally
gpt4_model = ChatOpenAI(model="gpt-4")
gpt35_model = ChatOpenAI(model="gpt-3.5-turbo")

def select_model(state: AgentState, runtime: Runtime[ModelContext]) -> ChatOpenAI:
    model_name = runtime.context.model_name
    model = gpt4_model if model_name == "gpt-4" else gpt35_model
    return model.bind_tools(tools)
```

Example 3 (unknown):
```unknown
- an OpenAI function/tool schema,
- a JSON Schema,
- a TypedDict class,
- or a Pydantic class.
- a tuple (prompt, schema), where schema is one of the above.
    The prompt will be used together with the model that is being used to generate the structured response.
```

Example 4 (unknown):
```unknown
# At least one of `messages` or `llm_input_messages` MUST be provided
{
    # If provided, will UPDATE the `messages` in the state
    "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), ...],
    # If provided, will be used as the input to the LLM,
    # and will NOT UPDATE `messages` in the state
    "llm_input_messages": [...],
    # Any other state keys that need to be propagated
    ...
}
```

---

## Reference¶

**URL:** https://langchain-ai.github.io/langgraph/reference/

**Contents:**
- Reference¶
- LangGraph¶
- Prebuilt components¶
- LangGraph Platform¶

Welcome to the LangGraph reference docs! These pages detail the core interfaces you will use when building with LangGraph. Each section covers a different part of the ecosystem.

If you are just getting started, see LangGraph basics for an introduction to the main concepts and usage patterns.

The core APIs for the LangGraph open source library.

Higher-level abstractions for common workflows, agents, and other patterns.

Tools for deploying and connecting to the LangGraph Platform.

See the LangGraph Platform reference for more reference documentation.

---

## 

**URL:** https://langchain-ai.github.io/langgraph/how-tos/create-react-agent/

---

## How to integrate LangGraph (functional API) with AutoGen, CrewAI, and other frameworks¶

**URL:** https://langchain-ai.github.io/langgraph/how-tos/autogen-integration-functional/

**Contents:**
- How to integrate LangGraph (functional API) with AutoGen, CrewAI, and other frameworks¶
- Setup¶
- Define AutoGen agent¶
- Create the workflow¶
- Run the graph¶

LangGraph is a framework for building agentic and multi-agent applications. LangGraph can be easily integrated with other agent frameworks.

The primary reasons you might want to integrate LangGraph with other agent frameworks:

The simplest way to integrate agents from other frameworks is by calling those agents inside a LangGraph node:

In this guide we show how to build a LangGraph chatbot that integrates with AutoGen, but you can follow the same approach with other frameworks.

import getpass import os def _set_env(var: str): if not os.environ.get(var): os.environ[var] = getpass.getpass(f"{var}: ") _set_env("OPENAI_API_KEY") OPENAI_API_KEY: ········

Here we define our AutoGen agent. Adapted from official tutorial here.

We will now create a LangGraph chatbot graph that calls AutoGen agent.

API Reference: convert_to_openai_messages | BaseMessage | entrypoint | task | add_messages | InMemorySaver

We can now run the graph.

# pass the thread ID to persist agent outputs for future interactions config = {"configurable": {"thread_id": "1"}} for chunk in workflow.stream( [ { "role": "user", "content": "Find numbers between 10 and 30 in fibonacci sequence", } ], config, ): print(chunk) user_proxy (to assistant): Find numbers between 10 and 30 in fibonacci sequence -------------------------------------------------------------------------------- assistant (to user_proxy): To find numbers between 10 and 30 in the Fibonacci sequence, we can generate the Fibonacci sequence and check which numbers fall within this range. Here's a plan: 1. Generate Fibonacci numbers starting from 0. 2. Continue generating until the numbers exceed 30. 3. Collect and print the numbers that are between 10 and 30. Let's implement this in Python: \`\`\`python # filename: fibonacci_range.py def fibonacci_sequence(): a, b = 0, 1 while a <= 30: if 10 <= a <= 30: print(a) a, b = b, a + b fibonacci_sequence() \`\`\` This script will print the Fibonacci numbers between 10 and 30. Please execute the code to see the result. -------------------------------------------------------------------------------- >>>>>>>> EXECUTING CODE BLOCK 0 (inferred language is python)... user_proxy (to assistant): exitcode: 0 (execution succeeded) Code output: 13 21 -------------------------------------------------------------------------------- assistant (to user_proxy): The Fibonacci numbers between 10 and 30 are 13 and 21. These numbers are part of the Fibonacci sequence, which is generated by adding the two preceding numbers to get the next number, starting from 0 and 1. The sequence goes: 0, 1, 1, 2, 3, 5, 8, 13, 21, 34, ... As you can see, 13 and 21 are the only numbers in this sequence that fall between 10 and 30. TERMINATE -------------------------------------------------------------------------------- {'call_autogen_agent': {'role': 'assistant', 'content': 'The Fibonacci numbers between 10 and 30 are 13 and 21. \n\nThese numbers are part of the Fibonacci sequence, which is generated by adding the two preceding numbers to get the next number, starting from 0 and 1. \n\nThe sequence goes: 0, 1, 1, 2, 3, 5, 8, 13, 21, 34, ...\n\nAs you can see, 13 and 21 are the only numbers in this sequence that fall between 10 and 30.\n\nTERMINATE'}} {'workflow': {'role': 'assistant', 'content': 'The Fibonacci numbers between 10 and 30 are 13 and 21. \n\nThese numbers are part of the Fibonacci sequence, which is generated by adding the two preceding numbers to get the next number, starting from 0 and 1. \n\nThe sequence goes: 0, 1, 1, 2, 3, 5, 8, 13, 21, 34, ...\n\nAs you can see, 13 and 21 are the only numbers in this sequence that fall between 10 and 30.\n\nTERMINATE'}} Since we're leveraging LangGraph's persistence features we can now continue the conversation using the same thread ID -- LangGraph will automatically pass previous history to the AutoGen agent:

for chunk in workflow.stream( [ { "role": "user", "content": "Multiply the last number by 3", } ], config, ): print(chunk) user_proxy (to assistant): Multiply the last number by 3 Context: Find numbers between 10 and 30 in fibonacci sequence The Fibonacci numbers between 10 and 30 are 13 and 21. These numbers are part of the Fibonacci sequence, which is generated by adding the two preceding numbers to get the next number, starting from 0 and 1. The sequence goes: 0, 1, 1, 2, 3, 5, 8, 13, 21, 34, ... As you can see, 13 and 21 are the only numbers in this sequence that fall between 10 and 30. TERMINATE -------------------------------------------------------------------------------- assistant (to user_proxy): The last number in the Fibonacci sequence between 10 and 30 is 21. Multiplying 21 by 3 gives: 21 * 3 = 63 TERMINATE -------------------------------------------------------------------------------- {'call_autogen_agent': {'role': 'assistant', 'content': 'The last number in the Fibonacci sequence between 10 and 30 is 21. Multiplying 21 by 3 gives:\n\n21 * 3 = 63\n\nTERMINATE'}} {'workflow': {'role': 'assistant', 'content': 'The last number in the Fibonacci sequence between 10 and 30 is 21. Multiplying 21 by 3 gives:\n\n21 * 3 = 63\n\nTERMINATE'}}

**Examples:**

Example 1 (python):
```python
import autogen
from langgraph.func import entrypoint, task

autogen_agent = autogen.AssistantAgent(name="assistant", ...)
user_proxy = autogen.UserProxyAgent(name="user_proxy", ...)

@task
def call_autogen_agent(messages):
    response = user_proxy.initiate_chat(
        autogen_agent,
        message=messages[-1],
        ...
    )
    ...


@entrypoint()
def workflow(messages):
    response = call_autogen_agent(messages).result()
    return response


workflow.invoke(
    [
        {
            "role": "user",
            "content": "Find numbers between 10 and 30 in fibonacci sequence",
        }
    ]
)
```

Example 2 (unknown):
```unknown
%pip install autogen langgraph
```

Example 3 (python):
```python
import getpass
import os


def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")


_set_env("OPENAI_API_KEY")
```

Example 4 (unknown):
```unknown
OPENAI_API_KEY:  ········
```

---

## How to force tool-calling agent to structure output¶

**URL:** https://langchain-ai.github.io/langgraph/how-tos/react-agent-structured-output/

**Contents:**
- How to force tool-calling agent to structure output¶
- Setup¶
- Define model, tools, and graph state¶
- Option 1: Bind output as tool¶
  - Define Graph¶
  - Usage¶
- Option 2: 2 LLMs¶
  - Define Graph¶
  - Usage¶

This guide assumes familiarity with the following: Structured Output Tool calling agent Chat Models Messages LangGraph Glossary

You might want your agent to return its output in a structured format. For example, if the output of the agent is used by some other downstream software, you may want the output to be in the same structured format every time the agent is invoked to ensure consistency.

This notebook will walk through two different options for forcing a tool calling agent to structure its output. We will be using a basic ReAct agent (a model node and a tool-calling node) together with a third node at the end that will format response for the user. Both of the options will use the same graph structure as shown in the diagram below, but will have different mechanisms under the hood.

The first way you can force your tool calling agent to have structured output is to bind the output you would like as an additional tool for the agent node to use. In contrast to the basic ReAct agent, the agent node in this case is not selecting between tools and END but rather selecting between the specific tools it calls. The expected flow in this case is that the LLM in the agent node will first select the action tool, and after receiving the action tool output it will call the response tool, which will then route to the respond node which simply structures the arguments from the agent node tool call.

The benefit to this format is that you only need one LLM, and can save money and latency because of this. The downside to this option is that it isn't guaranteed that the single LLM will call the correct tool when you want it to. We can help the LLM by setting tool_choice to any when we use bind_tools which forces the LLM to select at least one tool at every turn, but this is far from a foolproof strategy. In addition, another downside is that the agent might call multiple tools, so we need to check for this explicitly in our routing function (or if we are using OpenAI we can set parallell_tool_calling=False to ensure only one tool is called at a time).

The second way you can force your tool calling agent to have structured output is to use a second LLM (in this case model_with_structured_output) to respond to the user.

In this case, you will define a basic ReAct agent normally, but instead of having the agent node choose between the tools node and ending the conversation, the agent node will choose between the tools node and the respond node. The respond node will contain a second LLM that uses structured output, and once called will return directly to the user. You can think of this method as basic ReAct with one extra step before responding to the user.

The benefit of this method is that it guarantees structured output (as long as .with_structured_output works as expected with the LLM). The downside to using this approach is that it requires making an additional LLM call before responding to the user, which can increase costs as well as latency. In addition, by not providing the agent node LLM with information about the desired output schema there is a risk that the agent LLM will fail to call the correct tools required to answer in the correct output schema.

Note that both of these options will follow the exact same graph structure (see the diagram above), in that they are both exact replicas of the basic ReAct architecture but with a respond node before the end.

First, let's install the required packages and set our API keys

Set up LangSmith for LangGraph development

Sign up for LangSmith to quickly spot issues and improve the performance of your LangGraph projects. LangSmith lets you use trace data to debug, test, and monitor your LLM apps built with LangGraph — read more about how to get started here.

Now we can define how we want to structure our output, define our graph state, and also our tools and the models we are going to use.

To use structured output, we will use the with_structured_output method from LangChain, which you can read more about here.

We are going to use a single tool in this example for finding the weather, and will return a structured weather response to the user.

API Reference: tool | ChatAnthropic

Let's now examine how we would use the single LLM option.

The graph definition is very similar to the one above, the only difference is we no longer call an LLM in the response node, and instead bind the WeatherResponse tool to our LLM that already contains the get_weather tool.

API Reference: StateGraph | END | ToolNode

Now we can run our graph to check that it worked as intended:

Again, the agent returned a WeatherResponse object as we expected.

Let's now dive into how we would use a second LLM to force structured output.

We can now define our graph:

API Reference: StateGraph | END | ToolNode | HumanMessage

We can now invoke our graph to verify that the output is being structured as desired:

As we can see, the agent returned a WeatherResponse object as we expected. If would now be easy to use this agent in a more complex software stack without having to worry about the output of the agent not matching the format expected from the next step in the stack.

**Examples:**

Example 1 (unknown):
```unknown
pip install -U langgraph langchain_anthropic
```

Example 2 (python):
```python
import getpass
import os


def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")


_set_env("ANTHROPIC_API_KEY")
```

Example 3 (python):
```python
from pydantic import BaseModel, Field
from typing import Literal
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langgraph.graph import MessagesState


class WeatherResponse(BaseModel):
    """Respond to the user with this"""

    temperature: float = Field(description="The temperature in fahrenheit")
    wind_directon: str = Field(
        description="The direction of the wind in abbreviated form"
    )
    wind_speed: float = Field(description="The speed of the wind in km/h")


# Inherit 'messages' key from MessagesState, which is a list of chat messages
class AgentState(MessagesState):
    # Final structured response from the agent
    final_response: WeatherResponse


@tool
def get_weather(city: Literal["nyc", "sf"]):
    """Use this to get weather information."""
    if city == "nyc":
        return "It is cloudy in NYC, with 5 mph winds in the North-East direction and a temperature of 70 degrees"
    elif city == "sf":
        return "It is 75 degrees and sunny in SF, with 3 mph winds in the South-East direction"
    else:
        raise AssertionError("Unknown city")


tools = [get_weather]

model = ChatAnthropic(model="claude-3-opus-20240229")

model_with_tools = model.bind_tools(tools)
model_with_structured_output = model.with_structured_output(WeatherResponse)
```

Example 4 (python):
```python
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

tools = [get_weather, WeatherResponse]

# Force the model to use tools by passing tool_choice="any"
model_with_response_tool = model.bind_tools(tools, tool_choice="any")


# Define the function that calls the model
def call_model(state: AgentState):
    response = model_with_response_tool.invoke(state["messages"])
    # We return a list, because this will get added to the existing list
    return {"messages": [response]}


# Define the function that responds to the user
def respond(state: AgentState):
    # Construct the final answer from the arguments of the last tool call
    weather_tool_call = state["messages"][-1].tool_calls[0]
    response = WeatherResponse(**weather_tool_call["args"])
    # Since we're using tool calling to return structured output,
    # we need to add  a tool message corresponding to the WeatherResponse tool call,
    # This is due to LLM providers' requirement that AI messages with tool calls
    # need to be followed by a tool message for each tool call
    tool_message = {
        "type": "tool",
        "content": "Here is your structured response",
        "tool_call_id": weather_tool_call["id"],
    }
    # We return the final answer
    return {"final_response": response, "messages": [tool_message]}


# Define the function that determines whether to continue or not
def should_continue(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]
    # If there is only one tool call and it is the response tool call we respond to the user
    if (
        len(last_message.tool_calls) == 1
        and last_message.tool_calls[0]["name"] == "WeatherResponse"
    ):
        return "respond"
    # Otherwise we will use the tool node again
    else:
        return "continue"


# Define a new graph
workflow = StateGraph(AgentState)

# Define the two nodes we will cycle between
workflow.add_node("agent", call_model)
workflow.add_node("respond", respond)
workflow.add_node("tools", ToolNode(tools))

# Set the entrypoint as `agent`
# This means that this node is the first one called
workflow.set_entry_point("agent")

# We now add a conditional edge
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "continue": "tools",
        "respond": "respond",
    },
)

workflow.add_edge("tools", "agent")
workflow.add_edge("respond", END)
graph = workflow.compile()
```

---

## Stream outputs¶

**URL:** https://langchain-ai.github.io/langgraph/how-tos/streaming/

**Contents:**
- Stream outputs¶
- Supported stream modes¶
- Stream from an agent¶
  - Agent progress¶
  - LLM tokens¶
  - Tool updates¶
  - Stream multiple modes¶
  - Disable streaming¶
- Stream from a workflow¶
  - Basic usage example¶

You can stream outputs from a LangGraph agent or workflow.

Pass one or more of the following stream modes as a list to the stream() or astream() methods:

To stream agent progress, use the stream() or astream() methods with stream_mode="updates". This emits an event after every agent step.

For example, if you have an agent that calls a tool once, you should see the following updates:

To stream tokens as they are produced by the LLM, use stream_mode="messages":

To stream updates from tools as they are executed, you can use get_stream_writer.

If you add get_stream_writer inside your tool, you won't be able to invoke the tool outside of a LangGraph execution context.

You can specify multiple streaming modes by passing stream mode as a list: stream_mode=["updates", "messages", "custom"]:

In some applications you might need to disable streaming of individual tokens for a given model. This is useful in multi-agent systems to control which agents stream their output.

See the Models guide to learn how to disable streaming.

LangGraph graphs expose the .stream() (sync) and .astream() (async) methods to yield streamed outputs as iterators.

output {'refineTopic': {'topic': 'ice cream and cats'}} {'generateJoke': {'joke': 'This is a joke about ice cream and cats'}} |

You can pass a list as the stream_mode parameter to stream multiple modes at once.

The streamed outputs will be tuples of (mode, chunk) where mode is the name of the stream mode and chunk is the data streamed by that mode.

Use the stream modes updates and values to stream the state of the graph as it executes.

API Reference: StateGraph | START | END

Use this to stream only the state updates returned by the nodes after each step. The streamed outputs include the name of the node as well as the update.

Use this to stream the full state of the graph after each step.

To include outputs from subgraphs in the streamed outputs, you can set subgraphs=True in the .stream() method of the parent graph. This will stream outputs from both the parent graph and any subgraphs.

The outputs will be streamed as tuples (namespace, data), where namespace is a tuple with the path to the node where a subgraph is invoked, e.g. ("parent_node:<task_id>", "child_node:<task_id>").

Note that we are receiving not just the node updates, but we also the namespaces which tell us what graph (or subgraph) we are streaming from.

Use the debug streaming mode to stream as much information as possible throughout the execution of the graph. The streamed outputs include the name of the node as well as the full state.

Use the messages streaming mode to stream Large Language Model (LLM) outputs token by token from any part of your graph, including nodes, tools, subgraphs, or tasks.

The streamed output from messages mode is a tuple (message_chunk, metadata) where:

If your LLM is not available as a LangChain integration, you can stream its outputs using custom mode instead. See use with any LLM for details.

Manual config required for async in Python < 3.11

When using Python < 3.11 with async code, you must explicitly pass RunnableConfig to ainvoke() to enable proper streaming. See Async with Python < 3.11 for details or upgrade to Python 3.11+.

API Reference: init_chat_model | StateGraph | START

You can associate tags with LLM invocations to filter the streamed tokens by LLM invocation.

API Reference: init_chat_model

To stream tokens only from specific nodes, use stream_mode="messages" and filter the outputs by the langgraph_node field in the streamed metadata:

To send custom user-defined data from inside a LangGraph node or tool, follow these steps:

No get_stream_writer() in async for Python < 3.11

In async code running on Python < 3.11, get_stream_writer() will not work. Instead, add a writer parameter to your node or tool and pass it manually. See Async with Python < 3.11 for usage examples.

You can use stream_mode="custom" to stream data from any LLM API — even if that API does not implement the LangChain chat model interface.

This lets you integrate raw LLM clients or external services that provide their own streaming interfaces, making LangGraph highly flexible for custom setups.

API Reference: get_stream_writer

Let's invoke the graph with an AI message that includes a tool call:

If your application mixes models that support streaming with those that do not, you may need to explicitly disable streaming for models that do not support it.

Set disable_streaming=True when initializing the model.

In Python versions < 3.11, asyncio tasks do not support the context parameter. This limits LangGraph ability to automatically propagate context, and affects LangGraph's streaming mechanisms in two key ways:

**Examples:**

Example 1 (unknown):
```unknown
agent = create_react_agent(
    model="anthropic:claude-3-7-sonnet-latest",
    tools=[get_weather],
)
for chunk in agent.stream(
    {"messages": [{"role": "user", "content": "what is the weather in sf"}]},
    stream_mode="updates"
):
    print(chunk)
    print("\n")
```

Example 2 (unknown):
```unknown
agent = create_react_agent(
    model="anthropic:claude-3-7-sonnet-latest",
    tools=[get_weather],
)
async for chunk in agent.astream(
    {"messages": [{"role": "user", "content": "what is the weather in sf"}]},
    stream_mode="updates"
):
    print(chunk)
    print("\n")
```

Example 3 (unknown):
```unknown
agent = create_react_agent(
    model="anthropic:claude-3-7-sonnet-latest",
    tools=[get_weather],
)
for token, metadata in agent.stream(
    {"messages": [{"role": "user", "content": "what is the weather in sf"}]},
    stream_mode="messages"
):
    print("Token", token)
    print("Metadata", metadata)
    print("\n")
```

Example 4 (unknown):
```unknown
agent = create_react_agent(
    model="anthropic:claude-3-7-sonnet-latest",
    tools=[get_weather],
)
async for token, metadata in agent.astream(
    {"messages": [{"role": "user", "content": "what is the weather in sf"}]},
    stream_mode="messages"
):
    print("Token", token)
    print("Metadata", metadata)
    print("\n")
```

---

## Multi-agent supervisor¶

**URL:** https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor/

**Contents:**
- Multi-agent supervisor¶
- Setup¶
- 1. Create worker agents¶
  - Research agent¶
  - Math agent¶
- 2. Create supervisor with langgraph-supervisor¶
- 3. Create supervisor from scratch¶
  - Set up agent communication¶
  - Create supervisor agent¶
  - Create multi-agent graph¶

Supervisor is a multi-agent architecture where specialized agents are coordinated by a central supervisor agent. The supervisor agent controls all communication flow and task delegation, making decisions about which agent to invoke based on the current context and task requirements.

In this tutorial, you will build a supervisor system with two agents — a research and a math expert. By the end of the tutorial you will:

First, let's install required packages and set our API keys

Sign up for LangSmith to quickly spot issues and improve the performance of your LangGraph projects. LangSmith lets you use trace data to debug, test, and monitor your LLM apps built with LangGraph.

First, let's create our specialized worker agents — research agent and math agent:

For web search, we will use TavilySearch tool from langchain-tavily:

API Reference: TavilySearch

Output: Find events, attractions, deals, and more at nyctourism.com Skip Main Navigation Menu The Official Website of the City of New York Text Size Powered by Translate SearchSearch Primary Navigation The official website of NYC Home NYC Resources NYC311 Office of the Mayor Events Connect Jobs Search Office of the Mayor | Mayor's Bio | City of New York Secondary Navigation MayorBiographyNewsOfficials Eric L. Adams 110th Mayor of New York City Mayor Eric Adams has served the people of New York City as an NYPD officer, State Senator, Brooklyn Borough President, and now as the 110th Mayor of the City of New York. Mayor Eric Adams has served the people of New York City as an NYPD officer, State Senator, Brooklyn Borough President, and now as the 110th Mayor of the City of New York. He gave voice to a diverse coalition of working families in all five boroughs and is leading the fight to bring back New York City's economy, reduce inequality, improve public safety, and build a stronger, healthier city that delivers for all New Yorkers. As the representative of one of the nation's largest counties, Eric fought tirelessly to grow the local economy, invest in schools, reduce inequality, improve public safety, and advocate for smart policies and better government that delivers for all New Yorkers.

To create individual worker agents, we will use LangGraph's prebuilt agent.

API Reference: create_react_agent

Let's run the agent to verify that it behaves as expected.

We'll use pretty_print_messages helper to render the streamed agent outputs nicely

Output: Update from node agent: ================================== Ai Message ================================== Name: research_agent Tool Calls: tavily_search (call_U748rQhQXT36sjhbkYLSXQtJ) Call ID: call_U748rQhQXT36sjhbkYLSXQtJ Args: query: current mayor of New York City search_depth: basic Update from node tools: ================================= Tool Message ================================== Name: tavily_search {"query": "current mayor of New York City", "follow_up_questions": null, "answer": null, "images": [], "results": [{"title": "List of mayors of New York City - Wikipedia", "url": "https://en.wikipedia.org/wiki/List_of_mayors_of_New_York_City", "content": "The mayor of New York City is the chief executive of the Government of New York City, as stipulated by New York City's charter.The current officeholder, the 110th in the sequence of regular mayors, is Eric Adams, a member of the Democratic Party.. During the Dutch colonial period from 1624 to 1664, New Amsterdam was governed by the Director of Netherland.", "score": 0.9039154, "raw_content": null}, {"title": "Office of the Mayor | Mayor's Bio | City of New York - NYC.gov", "url": "https://www.nyc.gov/office-of-the-mayor/bio.page", "content": "Mayor Eric Adams has served the people of New York City as an NYPD officer, State Senator, Brooklyn Borough President, and now as the 110th Mayor of the City of New York. He gave voice to a diverse coalition of working families in all five boroughs and is leading the fight to bring back New York City's economy, reduce inequality, improve", "score": 0.8405867, "raw_content": null}, {"title": "Eric Adams - Wikipedia", "url": "https://en.wikipedia.org/wiki/Eric_Adams", "content": "Eric Leroy Adams (born September 1, 1960) is an American politician and former police officer who has served as the 110th mayor of New York City since 2022. Adams was an officer in the New York City Transit Police and then the New York City Police Department (```

For math agent tools we will use vanilla Python functions:

Let's run the math agent:

Output: Update from node agent: ================================== Ai Message ================================== Name: math_agent Tool Calls: add (call_p6OVLDHB4LyCNCxPOZzWR15v) Call ID: call_p6OVLDHB4LyCNCxPOZzWR15v Args: a: 3 b: 5 Update from node tools: ================================= Tool Message ================================== Name: add 8.0 Update from node agent: ================================== Ai Message ================================== Name: math_agent Tool Calls: multiply (call_EoaWHMLFZAX4AkajQCtZvbli) Call ID: call_EoaWHMLFZAX4AkajQCtZvbli Args: a: 8 b: 7 Update from node tools: ================================= Tool Message ================================== Name: multiply 56.0 Update from node agent: ================================== Ai Message ================================== Name: math_agent 56

To implement out multi-agent system, we will use create_supervisor from the prebuilt langgraph-supervisor library:

API Reference: create_supervisor | init_chat_model

Note: When you run this code, it will generate and display a visual representation of the supervisor graph showing the flow between the supervisor and worker agents.

Let's now run it with a query that requires both agents:

Output: Update from node supervisor: ================================= Tool Message ================================== Name: transfer_to_research_agent Successfully transferred to research_agent Update from node research_agent: ================================= Tool Message ================================== Name: transfer_back_to_supervisor Successfully transferred back to supervisor Update from node supervisor: ================================= Tool Message ================================== Name: transfer_to_math_agent Successfully transferred to math_agent Update from node math_agent: ================================= Tool Message ================================== Name: transfer_back_to_supervisor Successfully transferred back to supervisor Update from node supervisor: ================================== Ai Message ================================== Name: supervisor In 2024, the US GDP was $29.18 trillion and New York State's GDP was $2.297 trillion. New York State accounted for approximately 7.87% of the total US GDP in 2024.

Let's now implement this same multi-agent system from scratch. We will need to:

We will need to define a way for the supervisor agent to communicate with the worker agents. A common way to implement this in multi-agent architectures is using handoffs, where one agent hands off control to another. Handoffs allow you to specify:

We will implement handoffs via handoff tools and give these tools to the supervisor agent: when the supervisor calls these tools, it will hand off control to a worker agent, passing the full message history to that agent.

API Reference: tool | InjectedToolCallId | InjectedState | StateGraph | START | Command

Then, let's create the supervisor agent with the handoff tools we just defined. We will use the prebuilt create_react_agent:

Putting this all together, let's create a graph for our overall multi-agent system. We will add the supervisor and the individual agents as subgraph nodes.

Notice that we've added explicit edges from worker agents back to the supervisor — this means that they are guaranteed to return control back to the supervisor. If you want the agents to respond directly to the user (i.e., turn the system into a router, you can remove these edges).

Note: When you run this code, it will generate and display a visual representation of the multi-agent supervisor graph showing the flow between the supervisor and worker agents.

With the multi-agent graph created, let's now run it!

Output: Update from node supervisor: ================================= Tool Message ================================== Name: transfer_to_research_agent Successfully transferred to research_agent Update from node research_agent: ================================== Ai Message ================================== Name: research_agent - US GDP in 2024 is projected to be about $28.18 trillion USD (Statista; CBO projection). - New York State's nominal GDP for 2024 is estimated at approximately $2.16 trillion USD (various economic reports). - New York State's share of US GDP in 2024 is roughly 7.7%. Sources: - https://www.statista.com/statistics/216985/forecast-of-us-gross-domestic-product/ - https://nyassembly.gov/Reports/WAM/2025economic_revenue/2025_report.pdf?v=1740533306 Update from node supervisor: ================================= Tool Message ================================== Name: transfer_to_math_agent Successfully transferred to math_agent Update from node math_agent: ================================== Ai Message ================================== Name: math_agent US GDP in 2024: $28.18 trillion New York State GDP in 2024: $2.16 trillion Percentage of US GDP from New York State: 7.67% Update from node supervisor: ================================== Ai Message ================================== Name: supervisor Here are your results: - 2024 US GDP (projected): $28.18 trillion USD - 2024 New York State GDP (estimated): $2.16 trillion USD - New York State's share of US GDP: approximately 7.7% If you need the calculation steps or sources, let me know!

Let's examine the full resulting message history:

Output: ================================ Human Message ================================== find US and New York state GDP in 2024. what % of US GDP was New York state? ================================== Ai Message =================================== Name: supervisor Tool Calls: transfer_to_research_agent (call_KlGgvF5ahlAbjX8d2kHFjsC3) Call ID: call_KlGgvF5ahlAbjX8d2kHFjsC3 Args: ================================= Tool Message ================================== Name: transfer_to_research_agent Successfully transferred to research_agent ================================== Ai Message =================================== Name: research_agent Tool Calls: tavily_search (call_ZOaTVUA6DKrOjWQldLhtrsO2) Call ID: call_ZOaTVUA6DKrOjWQldLhtrsO2 Args: query: US GDP 2024 estimate or actual search_depth: advanced tavily_search (call_QsRAasxW9K03lTlqjuhNLFbZ) Call ID: call_QsRAasxW9K03lTlqjuhNLFbZ Args: query: New York state GDP 2024 estimate or actual search_depth: advanced ================================= Tool Message ================================== Name: tavily_search {"query": "US GDP 2024 estimate or actual", "follow_up_questions": null, "answer": null, "images": [], "results": [{"url": "https://www.advisorperspectives.com/dshort/updates/2025/05/29/gdp-gross-domestic-product-q1-2025-second-estimate", "title": "Q1 GDP Second Estimate: Real GDP at -0.2%, Higher Than Expected", "content": "> Real gross domestic product (GDP) decreased at an annual rate of 0.2 percent in the first quarter of 2025 (January, February, and March), according to the second estimate released by the U.S. Bureau of Economic Analysis. In the fourth quarter of 2024, real GDP increased 2.4 percent. The decrease in real GDP in the first quarter primarily reflected an increase in imports, which are a subtraction in the calculation of GDP, and a decrease in government spending. These movements were partly [...] by [Harry Mamaysky](https://www.advisor```

You can see that the supervisor system appends all of the individual agent messages (i.e., their internal tool-calling loop) to the full message history. This means that on every supervisor turn, supervisor agent sees this full history. If you want more control over:

how agent outputs are added: you can control how much of the agent's internal message history is added to the overall supervisor message history by wrapping the agent in a separate node function:

So far the individual agents relied on interpreting full message history to determine their tasks. An alternative approach is to ask the supervisor to formulate a task explicitly. We can do so by adding a task_description parameter to the handoff_tool function.

We're using Send() primitive in the handoff_tool. This means that instead of receiving the full supervisor graph state as input, each worker agent only sees the contents of the Send payload. In this example, we're sending the task description as a single "human" message.

Let's now running it with the same input query:

Output: Update from subgraph supervisor: Update from node agent: ================================== Ai Message ================================== Name: supervisor Tool Calls: transfer_to_research_agent (call_tk8q8py8qK6MQz6Kj6mijKua) Call ID: call_tk8q8py8qK6MQz6Kj6mijKua Args: task_description: Find the 2024 GDP (Gross Domestic Product) for both the United States and New York state, using the most up-to-date and reputable sources available. Provide both GDP values and cite the data sources. Update from subgraph research_agent: Update from node agent: ================================== Ai Message ================================== Name: research_agent Tool Calls: tavily_search (call_KqvhSvOIhAvXNsT6BOwbPlRB) Call ID: call_KqvhSvOIhAvXNsT6BOwbPlRB Args: query: 2024 United States GDP value from a reputable source search_depth: advanced tavily_search (call_kbbAWBc9KwCWKHmM5v04H88t) Call ID: call_kbbAWBc9KwCWKHmM5v04H88t Args: query: 2024 New York state GDP value from a reputable source search_depth: advanced Update from subgraph research_agent: Update from node tools: ================================= Tool Message ================================== Name: tavily_search {"query": "2024 United States GDP value from a reputable source", "follow_up_questions": null, "answer": null, "images": [], "results": [{"url": "https://www.focus-economics.com/countries/united-states/", "title": "United States Economy Overview - Focus Economics", "content": "The United States' Macroeconomic Analysis:\n------------------------------------------\n\n**Nominal GDP of USD 29,185 billion in 2024.**\n\n**Nominal GDP of USD 29,179 billion in 2024.**\n\n**GDP per capita of USD 86,635 compared to the global average of USD 10,589.**\n\n**GDP per capita of USD 86,652 compared to the global average of USD 10,589.**\n\n**Average real GDP growth of 2.5% over the last decade.**\n\n**Average real GDP growth of ```

**Examples:**

Example 1 (unknown):
```unknown
%%capture --no-stderr
%pip install -U langgraph langgraph-supervisor langchain-tavily "langchain[openai]"
```

Example 2 (python):
```python
import getpass
import os


def _set_if_undefined(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"Please provide your {var}")


_set_if_undefined("OPENAI_API_KEY")
_set_if_undefined("TAVILY_API_KEY")
```

Example 3 (python):
```python
from langchain_tavily import TavilySearch

web_search = TavilySearch(max_results=3)
web_search_results = web_search.invoke("who is the mayor of NYC?")

print(web_search_results["results"][0]["content"])
```

Example 4 (unknown):
```unknown
Find events, attractions, deals, and more at nyctourism.com Skip Main Navigation Menu The Official Website of the City of New York Text Size Powered by Translate SearchSearch Primary Navigation The official website of NYC Home NYC Resources NYC311 Office of the Mayor Events Connect Jobs Search Office of the Mayor | Mayor's Bio | City of New York Secondary Navigation MayorBiographyNewsOfficials Eric L. Adams 110th Mayor of New York City Mayor Eric Adams has served the people of New York City as an NYPD officer, State Senator, Brooklyn Borough President, and now as the 110th Mayor of the City of New York. Mayor Eric Adams has served the people of New York City as an NYPD officer, State Senator, Brooklyn Borough President, and now as the 110th Mayor of the City of New York. He gave voice to a diverse coalition of working families in all five boroughs and is leading the fight to bring back New York City's economy, reduce inequality, improve public safety, and build a stronger, healthier city that delivers for all New Yorkers. As the representative of one of the nation's largest counties, Eric fought tirelessly to grow the local economy, invest in schools, reduce inequality, improve public safety, and advocate for smart policies and better government that delivers for all New Yorkers.
```

---

## How to create a ReAct agent from scratch (Functional API)¶

**URL:** https://langchain-ai.github.io/langgraph/how-tos/react-agent-from-scratch-functional/

**Contents:**
- How to create a ReAct agent from scratch (Functional API)¶
- Setup¶
- Create ReAct agent¶
  - Define model and tools¶
  - Define tasks¶
  - Define entrypoint¶
- Usage¶
- Add thread-level persistence¶

This guide assumes familiarity with the following:

This guide demonstrates how to implement a ReAct agent using the LangGraph Functional API.

The ReAct agent is a tool-calling agent that operates as follows:

This is a simple and versatile set-up that can be extended with memory, human-in-the-loop capabilities, and other features. See the dedicated how-to guides for examples.

First, let's install the required packages and set our API keys:

Set up LangSmith for better debugging

Sign up for LangSmith to quickly spot issues and improve the performance of your LangGraph projects. LangSmith lets you use trace data to debug, test, and monitor your LLM aps built with LangGraph — read more about how to get started in the docs.

Now that you have installed the required packages and set your environment variables, we can create our agent.

Let's first define the tools and model we will use for our example. Here we will use a single place-holder tool that gets a description of the weather for a location.

We will use an OpenAI chat model for this example, but any model supporting tool-calling will suffice.

API Reference: ChatOpenAI | tool

We next define the tasks we will execute. Here there are two different tasks:

API Reference: ToolMessage | entrypoint | task

Our entrypoint will handle the orchestration of these two tasks. As described above, when our call_model task generates tool calls, the call_tool task will generate responses for each. We append all messages to a single messages list.

Note that because tasks return future-like objects, the below implementation executes tools in parallel.

API Reference: add_messages

To use our agent, we invoke it with a messages list. Based on our implementation, these can be LangChain message objects or OpenAI-style dicts:

user_message = {"role": "user", "content": "What's the weather in san francisco?"} print(user_message) for step in agent.stream([user_message]): for task_name, message in step.items(): if task_name == "agent": continue # Just print task updates print(f"\n{task_name}:") message.pretty_print() {'role': 'user', 'content': "What's the weather in san francisco?"} call_model: ================================== Ai Message ================================== Tool Calls: get_weather (call_tNnkrjnoz6MNfCHJpwfuEQ0v) Call ID: call_tNnkrjnoz6MNfCHJpwfuEQ0v Args: location: san francisco call_tool: ================================= Tool Message ================================= It's sunny! call_model: ================================== Ai Message ================================== The weather in San Francisco is sunny! Perfect! The graph correctly calls the get_weather tool and responds to the user after receiving the information from the tool. Check out the LangSmith trace here.

Adding thread-level persistence lets us support conversational experiences with our agent: subsequent invocations will append to the prior messages list, retaining the full conversational context.

To add thread-level persistence to our agent:

API Reference: InMemorySaver

We will now need to pass in a config when running our application. The config will specify an identifier for the conversational thread.

Read more about thread-level persistence in our concepts page and how-to guides.

We start a thread the same way as before, this time passing in the config:

user_message = {"role": "user", "content": "What's the weather in san francisco?"} print(user_message) for step in agent.stream([user_message], config): for task_name, message in step.items(): if task_name == "agent": continue # Just print task updates print(f"\n{task_name}:") message.pretty_print() {'role': 'user', 'content': "What's the weather in san francisco?"} call_model: ================================== Ai Message ================================== Tool Calls: get_weather (call_lubbUSdDofmOhFunPEZLBz3g) Call ID: call_lubbUSdDofmOhFunPEZLBz3g Args: location: San Francisco call_tool: ================================= Tool Message ================================= It's sunny! call_model: ================================== Ai Message ================================== The weather in San Francisco is sunny! When we ask a follow-up conversation, the model uses the prior context to infer that we are asking about the weather:

user_message = {"role": "user", "content": "How does it compare to Boston, MA?"} print(user_message) for step in agent.stream([user_message], config): for task_name, message in step.items(): if task_name == "agent": continue # Just print task updates print(f"\n{task_name}:") message.pretty_print() {'role': 'user', 'content': 'How does it compare to Boston, MA?'} call_model: ================================== Ai Message ================================== Tool Calls: get_weather (call_8sTKYAhSIHOdjLD5d6gaswuV) Call ID: call_8sTKYAhSIHOdjLD5d6gaswuV Args: location: Boston, MA call_tool: ================================= Tool Message ================================= It's rainy! call_model: ================================== Ai Message ================================== Compared to San Francisco, which is sunny, Boston, MA is experiencing rainy weather. In the LangSmith trace, we can see that the full conversational context is retained in each model call.

**Examples:**

Example 1 (unknown):
```unknown
pip install -U langgraph langchain-openai
```

Example 2 (python):
```python
import getpass
import os


def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")


_set_env("OPENAI_API_KEY")
```

Example 3 (python):
```python
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

model = ChatOpenAI(model="gpt-4o-mini")


@tool
def get_weather(location: str):
    """Call to get the weather from a specific location."""
    # This is a placeholder for the actual implementation
    if any([city in location.lower() for city in ["sf", "san francisco"]]):
        return "It's sunny!"
    elif "boston" in location.lower():
        return "It's rainy!"
    else:
        return f"I am not sure what the weather is in {location}"


tools = [get_weather]
```

Example 4 (python):
```python
from langchain_core.messages import ToolMessage
from langgraph.func import entrypoint, task

tools_by_name = {tool.name: tool for tool in tools}


@task
def call_model(messages):
    """Call model with a sequence of messages."""
    response = model.bind_tools(tools).invoke(messages)
    return response


@task
def call_tool(tool_call):
    tool = tools_by_name[tool_call["name"]]
    observation = tool.invoke(tool_call["args"])
    return ToolMessage(content=observation, tool_call_id=tool_call["id"])
```

---

## How to build a multi-agent network (functional API)¶

**URL:** https://langchain-ai.github.io/langgraph/how-tos/multi-agent-network-functional/

**Contents:**
- How to build a multi-agent network (functional API)¶
- Setup¶
- Travel agent example¶

This guide assumes familiarity with the following:

In this how-to guide we will demonstrate how to implement a multi-agent network architecture where each agent can communicate with every other agent (many-to-many connections) and can decide which agent to call next. We will be using functional API — individual agents will be defined as tasks and the agent handoffs will be defined in the main entrypoint():

API Reference: entrypoint | create_react_agent | tool

First, let's install the required packages

import getpass import os def _set_env(var: str): if not os.environ.get(var): os.environ[var] = getpass.getpass(f"{var}: ") _set_env("ANTHROPIC_API_KEY") ANTHROPIC_API_KEY: ········

Set up LangSmith for LangGraph development

Sign up for LangSmith to quickly spot issues and improve the performance of your LangGraph projects. LangSmith lets you use trace data to debug, test, and monitor your LLM apps built with LangGraph — read more about how to get started here.

In this example we will build a team of travel assistant agents that can communicate with each other.

We will create 2 agents:

This is a fully-connected network - every agent can talk to any other agent.

First, let's create some of the tools that the agents will be using:

You might have noticed that we're using @tool(return_direct=True) in the transfer tools. This is done so that individual agents (e.g., travel_advisor) can exit the ReAct loop early once these tools are called. This is the desired behavior, as we want to detect when the agent calls this tool and hand control off immediately to a different agent.

NOTE: This is meant to work with the prebuilt create_react_agent -- if you are building a custom agent, make sure to manually add logic for handling early exit for tools that are marked with return_direct.

Now let's define our agent tasks and combine them into a single multi-agent network workflow:

API Reference: AIMessage | ChatAnthropic | create_react_agent | add_messages | entrypoint | task

Lastly, let's define a helper to render the agent outputs:

API Reference: convert_to_messages

Let's test it out using the same input as our original multi-agent system:

for chunk in workflow.stream( [ { "role": "user", "content": "i wanna go somewhere warm in the caribbean. pick one destination and give me hotel recommendations", } ], subgraphs=True, ): pretty_print_messages(chunk) Update from subgraph call_travel_advisor: Update from node agent: ================================== Ai Message ================================== [{'text': "I'll help you find a warm Caribbean destination and then get some hotel recommendations for you.\n\nLet me first get some destination recommendations for the Caribbean region.", 'type': 'text'}, {'id': 'toolu_015vT8PkPq1VXvjrDvSpWUwJ', 'input': {}, 'name': 'get_travel_recommendations', 'type': 'tool_use'}] Tool Calls: get_travel_recommendations (toolu_015vT8PkPq1VXvjrDvSpWUwJ) Call ID: toolu_015vT8PkPq1VXvjrDvSpWUwJ Args: Update from subgraph call_travel_advisor: Update from node tools: ================================= Tool Message ================================= Name: get_travel_recommendations turks and caicos Update from subgraph call_travel_advisor: Update from node agent: ================================== Ai Message ================================== [{'text': "Based on the recommendation, I suggest Turks and Caicos! This beautiful British Overseas Territory is known for its stunning white-sand beaches, crystal-clear turquoise waters, and year-round warm weather. Grace Bay Beach in Providenciales is consistently ranked among the world's best beaches. The islands offer excellent snorkeling, diving, and water sports opportunities, plus a relaxed Caribbean atmosphere.\n\nNow, let me connect you with our hotel advisor to get some specific hotel recommendations for Turks and Caicos.", 'type': 'text'}, {'id': 'toolu_01JY7pNNWFuaWoe9ymxFYiPV', 'input': {}, 'name': 'transfer_to_hotel_advisor', 'type': 'tool_use'}] Tool Calls: transfer_to_hotel_advisor (toolu_01JY7pNNWFuaWoe9ymxFYiPV) Call ID: toolu_01JY7pNNWFuaWoe9ymxFYiPV Args: Update from subgraph call_travel_advisor: Update from node tools: ================================= Tool Message ================================= Name: transfer_to_hotel_advisor Successfully transferred to hotel advisor Update from subgraph call_hotel_advisor: Update from node agent: ================================== Ai Message ================================== [{'text': 'Let me get some hotel recommendations for Turks and Caicos:', 'type': 'text'}, {'id': 'toolu_0129ELa7jFocn16bowaGNapg', 'input': {'location': 'turks and caicos'}, 'name': 'get_hotel_recommendations', 'type': 'tool_use'}] Tool Calls: get_hotel_recommendations (toolu_0129ELa7jFocn16bowaGNapg) Call ID: toolu_0129ELa7jFocn16bowaGNapg Args: location: turks and caicos Update from subgraph call_hotel_advisor: Update from node tools: ================================= Tool Message ================================= Name: get_hotel_recommendations ["Grace Bay Club", "COMO Parrot Cay"] Update from subgraph call_hotel_advisor: Update from node agent: ================================== Ai Message ================================== Here are two excellent hotel options in Turks and Caicos: 1. Grace Bay Club: This luxury resort is located on the world-famous Grace Bay Beach. It offers all-oceanfront suites, exceptional dining options, and personalized service. The resort features adult-only and family-friendly sections, making it perfect for any type of traveler. 2. COMO Parrot Cay: This exclusive private island resort offers the ultimate luxury escape. It's known for its pristine beach, world-class spa, and holistic wellness programs. The resort provides an intimate, secluded experience with top-notch amenities and service. Would you like more specific information about either of these properties or would you like to explore hotels in another destination? Voila - travel_advisor picks a destination and then makes a decision to call hotel_advisor for more info!

**Examples:**

Example 1 (python):
```python
from langgraph.func import entrypoint
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool


# Define a tool to signal intent to hand off to a different agent
@tool(return_direct=True)
def transfer_to_hotel_advisor():
    """Ask hotel advisor agent for help."""
    return "Successfully transferred to hotel advisor"


# define an agent
travel_advisor_tools = [transfer_to_hotel_advisor, ...]
travel_advisor = create_react_agent(model, travel_advisor_tools)


# define a task that calls an agent
@task
def call_travel_advisor(messages):
    response = travel_advisor.invoke({"messages": messages})
    return response["messages"]


# define the multi-agent network workflow
@entrypoint()
def workflow(messages):
    call_active_agent = call_travel_advisor
    while True:
        agent_messages = call_active_agent(messages).result()
        messages = messages + agent_messages
        call_active_agent = get_next_agent(messages)
    return messages
```

Example 2 (unknown):
```unknown
pip install -U langgraph langchain-anthropic
```

Example 3 (python):
```python
import getpass
import os


def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")


_set_env("ANTHROPIC_API_KEY")
```

Example 4 (unknown):
```unknown
ANTHROPIC_API_KEY:  ········
```

---

## How to add multi-turn conversation in a multi-agent application (functional API)¶

**URL:** https://langchain-ai.github.io/langgraph/how-tos/multi-agent-multi-turn-convo-functional/

**Contents:**
- How to add multi-turn conversation in a multi-agent application (functional API)¶
- Setup¶
- Test multi-turn conversation¶

This guide assumes familiarity with the following:

In this how-to guide, we’ll build an application that allows an end-user to engage in a multi-turn conversation with one or more agents. We'll create a node that uses an interrupt to collect user input and routes back to the active agent.

The agents will be implemented as tasks in a workflow that executes agent steps and determines the next action:

API Reference: entrypoint | task | create_react_agent | tool | interrupt

First, let's install the required packages

import getpass import os def _set_env(var: str): if not os.environ.get(var): os.environ[var] = getpass.getpass(f"{var}: ") _set_env("ANTHROPIC_API_KEY") ANTHROPIC_API_KEY: ········

Set up LangSmith for LangGraph development

Sign up for LangSmith to quickly spot issues and improve the performance of your LangGraph projects. LangSmith lets you use trace data to debug, test, and monitor your LLM apps built with LangGraph — read more about how to get started here.

In this example we will build a team of travel assistant agents that can communicate with each other.

We will create 2 agents:

This is a fully-connected network - every agent can talk to any other agent.

You might have noticed that we're using @tool(return_direct=True) in the transfer tools. This is done so that individual agents (e.g., travel_advisor) can exit the ReAct loop early once these tools are called. This is the desired behavior, as we want to detect when the agent calls this tool and hand control off immediately to a different agent.

NOTE: This is meant to work with the prebuilt create_react_agent -- if you are building a custom agent, make sure to manually add logic for handling early exit for tools that are marked with return_direct.

Let's now create our agents using the prebuilt create_react_agent and our multi-agent workflow. Note that will be calling interrupt every time after we get the final response from each of the agents.

API Reference: AIMessage | ChatAnthropic | create_react_agent | add_messages | entrypoint | task | InMemorySaver | interrupt | Command

Let's test a multi turn conversation with this application.

thread_config = {"configurable": {"thread_id": uuid.uuid4()}} inputs = [ # 1st round of conversation, { "role": "user", "content": "i wanna go somewhere warm in the caribbean", "id": str(uuid.uuid4()), }, # Since we're using `interrupt`, we'll need to resume using the Command primitive. # 2nd round of conversation, Command( resume="could you recommend a nice hotel in one of the areas and tell me which area it is." ), # 3rd round of conversation, Command( resume="i like the first one. could you recommend something to do near the hotel?" ), ] for idx, user_input in enumerate(inputs): print() print(f"--- Conversation Turn {idx + 1} ---") print() print(f"User: {user_input}") print() for update in multi_turn_graph.stream( user_input, config=thread_config, stream_mode="updates", ): for node_id, value in update.items(): if isinstance(value, list) and value: last_message = value[-1] if isinstance(last_message, dict) or last_message.type != "ai": continue print(f"{node_id}: {last_message.content}") --- Conversation Turn 1 --- User: {'role': 'user', 'content': 'i wanna go somewhere warm in the caribbean', 'id': 'f48d82a7-7efa-43f5-ad4c-541758c95f61'} call_travel_advisor: Based on the recommendations, Aruba would be an excellent choice for your Caribbean getaway! Known as "One Happy Island," Aruba offers: - Year-round warm weather with consistent temperatures around 82°F (28°C) - Beautiful white sand beaches like Eagle Beach and Palm Beach - Crystal clear waters perfect for swimming and snorkeling - Minimal rainfall and location outside the hurricane belt - Rich culture blending Dutch and Caribbean influences - Various activities from water sports to desert-like landscape exploration - Excellent dining and shopping options Would you like me to help you find suitable accommodations in Aruba? I can transfer you to our hotel advisor who can recommend specific hotels based on your preferences. --- Conversation Turn 2 --- User: Command(resume='could you recommend a nice hotel in one of the areas and tell me which area it is.') call_hotel_advisor: I can recommend two excellent options in different areas: 1. The Ritz-Carlton, Aruba - Located in Palm Beach - Luxury beachfront resort - Located in the vibrant Palm Beach area, known for its lively atmosphere - Close to restaurants, shopping, and nightlife - Perfect for those who want a more active vacation with plenty of amenities nearby 2. Bucuti & Tara Beach Resort - Located in Eagle Beach - Adults-only boutique resort - Situated on the quieter Eagle Beach - Known for its romantic atmosphere and excellent service - Ideal for couples seeking a more peaceful, intimate setting Would you like more specific information about either of these properties or their locations? --- Conversation Turn 3 --- User: Command(resume='i like the first one. could you recommend something to do near the hotel?') call_travel_advisor: Near The Ritz-Carlton in Palm Beach, here are some popular activities you can enjoy: 1. Palm Beach Strip - Take a walk along this bustling strip filled with restaurants, shops, and bars 2. Visit the Bubali Bird Sanctuary - Just a short distance away 3. Try your luck at the Stellaris Casino - Located right in The Ritz-Carlton 4. Water Sports at Palm Beach - Right in front of the hotel you can: - Go parasailing - Try jet skiing - Take a sunset sailing cruise 5. Visit the Palm Beach Plaza Mall - High-end shopping just a short walk away 6. Enjoy dinner at Madame Janette's - One of Aruba's most famous restaurants nearby Would you like more specific information about any of these activities or other suggestions in the area?

**Examples:**

Example 1 (python):
```python
from langgraph.func import entrypoint, task
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from langgraph.types import interrupt


# Define a tool to signal intent to hand off to a different agent
# Note: this is not using Command(goto) syntax for navigating to different agents:
# `workflow()` below handles the handoffs explicitly
@tool(return_direct=True)
def transfer_to_hotel_advisor():
    """Ask hotel advisor agent for help."""
    return "Successfully transferred to hotel advisor"


# define an agent
travel_advisor_tools = [transfer_to_hotel_advisor, ...]
travel_advisor = create_react_agent(model, travel_advisor_tools)


# define a task that calls an agent
@task
def call_travel_advisor(messages):
    response = travel_advisor.invoke({"messages": messages})
    return response["messages"]


# define the multi-agent network workflow
@entrypoint(checkpointer)
def workflow(messages):
    call_active_agent = call_travel_advisor
    while True:
        agent_messages = call_active_agent(messages).result()
        ai_msg = get_last_ai_msg(agent_messages)
        if not ai_msg.tool_calls:
            user_input = interrupt(value="Ready for user input.")
            messages = messages + [{"role": "user", "content": user_input}]
            continue

        messages = messages + agent_messages
        call_active_agent = get_next_agent(messages)
    return entrypoint.final(value=agent_messages[-1], save=messages)
```

Example 2 (unknown):
```unknown
# %%capture --no-stderr
# %pip install -U langgraph langchain-anthropic
```

Example 3 (python):
```python
import getpass
import os


def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")


_set_env("ANTHROPIC_API_KEY")
```

Example 4 (unknown):
```unknown
ANTHROPIC_API_KEY:  ········
```

---

## LangGraph Supervisor¶

**URL:** https://langchain-ai.github.io/langgraph/reference/supervisor/

**Contents:**
- LangGraph Supervisor¶
- create_supervisor ¶
- create_handoff_tool ¶
- create_forward_message_tool ¶

Create a multi-agent supervisor.

Create a multi-agent supervisor.

List of agents to manage. An agent can be a LangGraph CompiledStateGraph, a functional API workflow, or any other Pregel object.

Language model to use for the supervisor

Tools to use for the supervisor

Optional prompt to use for the supervisor. Can be one of:

An optional schema for the final supervisor output.

If provided, output will be formatted to match the given schema and returned in the 'structured_response' state key. If not provided, structured_response will not be present in the output state. Can be passed in as:

response_format requires the model to support .with_structured_output

response_format requires structured_response key in your state schema. You can use the prebuilt langgraph.prebuilt.chat_agent_executor.AgentStateWithStructuredResponse.

An optional node to add before the LLM node in the supervisor agent (i.e., the node that calls the LLM). Useful for managing long message histories (e.g., message trimming, summarization, etc.). Pre-model hook must be a callable or a runnable that takes in current graph state and returns a state update in the form of # At least one of `messages` or `llm_input_messages` MUST be provided { # If provided, will UPDATE the `messages` in the state "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), ...], # If provided, will be used as the input to the LLM, # and will NOT UPDATE `messages` in the state "llm_input_messages": [...], # Any other state keys that need to be propagated ... }

At least one of messages or llm_input_messages MUST be provided and will be used as an input to the agent node. The rest of the keys will be added to the graph state.

If you are returning messages in the pre-model hook, you should OVERWRITE the messages key by doing the following:

An optional node to add after the LLM node in the supervisor agent (i.e., the node that calls the LLM). Useful for implementing human-in-the-loop, guardrails, validation, or other post-processing. Post-model hook must be a callable or a runnable that takes in current graph state and returns a state update.

Only available with langgraph-prebuilt>=0.2.0.

Whether to allow the supervisor LLM to call tools in parallel (only OpenAI and Anthropic). Use this to control whether the supervisor can hand off to multiple agents at once. If True, will enable parallel tool calls. If False, will disable parallel tool calls (default).

This is currently supported only by OpenAI and Anthropic models. To control parallel tool calling for other providers, add explicit instructions for tool use to the system prompt.

State schema to use for the supervisor graph.

An optional schema for configuration. Use this to expose configurable parameters via supervisor.config_specs.

Mode for adding managed agents' outputs to the message history in the multi-agent workflow. Can be one of:

Whether to add a pair of (AIMessage, ToolMessage) to the message history when a handoff occurs.

Optional prefix for the handoff tools (e.g., "delegate_to_" or "transfer_to_") If provided, the handoff tools will be named handoff_tool_prefix_agent_name. If not provided, the handoff tools will be named transfer_to_agent_name.

Whether to add a pair of (AIMessage, ToolMessage) to the message history when returning control to the supervisor to indicate that a handoff has occurred.

Name of the supervisor node.

Use to specify how to expose the agent name to the underlying supervisor LLM.

Create a tool that can handoff control to the requested agent.

Create a tool the supervisor can use to forward a worker message by name.

Create a tool that can handoff control to the requested agent.

The name of the agent to handoff control to, i.e. the name of the agent node in the multi-agent graph. Agent names should be simple, clear and unique, preferably in snake_case, although you are only limited to the names accepted by LangGraph nodes as well as the tool names accepted by LLM providers (the tool name will look like this: transfer_to_<agent_name>).

Optional name of the tool to use for the handoff. If not provided, the tool name will be transfer_to_<agent_name>.

Optional description for the handoff tool. If not provided, the description will be Ask agent <agent_name> for help.

Whether to add handoff messages to the message history. If False, the handoff messages will be omitted from the message history.

Create a tool the supervisor can use to forward a worker message by name.

This helps avoid information loss any time the supervisor rewrites a worker query to the user and also can save some tokens.

The name of the supervisor node (used for namespacing the tool).

The 'forward_message' tool.

**Examples:**

Example 1 (unknown):
```unknown
create_supervisor(
    agents: list[Pregel],
    *,
    model: LanguageModelLike,
    tools: (
        list[BaseTool | Callable] | ToolNode | None
    ) = None,
    prompt: Prompt | None = None,
    response_format: Optional[
        Union[
            StructuredResponseSchema,
            tuple[str, StructuredResponseSchema],
        ]
    ] = None,
    pre_model_hook: Optional[RunnableLike] = None,
    post_model_hook: Optional[RunnableLike] = None,
    parallel_tool_calls: bool = False,
    state_schema: StateSchemaType | None = None,
    config_schema: Type[Any] | None = None,
    output_mode: OutputMode = "last_message",
    add_handoff_messages: bool = True,
    handoff_tool_prefix: Optional[str] = None,
    add_handoff_back_messages: Optional[bool] = None,
    supervisor_name: str = "supervisor",
    include_agent_name: AgentNameMode | None = None
) -> StateGraph
```

Example 2 (unknown):
```unknown
- an OpenAI function/tool schema,
- a JSON Schema,
- a TypedDict class,
- or a Pydantic class.
- a tuple (prompt, schema), where schema is one of the above.
    The prompt will be used together with the model that is being used to generate the structured response.
```

Example 3 (unknown):
```unknown
# At least one of `messages` or `llm_input_messages` MUST be provided
{
    # If provided, will UPDATE the `messages` in the state
    "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), ...],
    # If provided, will be used as the input to the LLM,
    # and will NOT UPDATE `messages` in the state
    "llm_input_messages": [...],
    # Any other state keys that need to be propagated
    ...
}
```

Example 4 (unknown):
```unknown
{
    "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *new_messages]
    ...
}
```

---

## Workflows and Agents¶

**URL:** https://langchain-ai.github.io/langgraph/tutorials/workflows/

**Contents:**
- Workflows and Agents¶
- Set up¶
- Building Blocks: The Augmented LLM¶
- Prompt chaining¶
- Parallelization¶
- Routing¶
- Orchestrator-Worker¶
- Evaluator-optimizer¶
- Agent¶
    - Pre-built¶

This guide reviews common patterns for agentic systems. In describing these systems, it can be useful to make a distinction between "workflows" and "agents". One way to think about this difference is nicely explained in Anthropic's Building Effective Agents blog post:

Workflows are systems where LLMs and tools are orchestrated through predefined code paths. Agents, on the other hand, are systems where LLMs dynamically direct their own processes and tool usage, maintaining control over how they accomplish tasks.

Here is a simple way to visualize these differences:

When building agents and workflows, LangGraph offers a number of benefits including persistence, streaming, and support for debugging as well as deployment.

You can use any chat model that supports structured outputs and tool calling. Below, we show the process of installing the packages, setting API keys, and testing structured outputs / tool calling for Anthropic.

API Reference: ChatAnthropic

LLM have augmentations that support building workflows and agents. These include structured outputs and tool calling, as shown in this image from the Anthropic blog on Building Effective Agents:

In prompt chaining, each LLM call processes the output of the previous one.

As noted in the Anthropic blog on Building Effective Agents:

Prompt chaining decomposes a task into a sequence of steps, where each LLM call processes the output of the previous one. You can add programmatic checks (see "gate" in the diagram below) on any intermediate steps to ensure that the process is still on track.

When to use this workflow: This workflow is ideal for situations where the task can be easily and cleanly decomposed into fixed subtasks. The main goal is to trade off latency for higher accuracy, by making each LLM call an easier task.

https://smith.langchain.com/public/a0281fca-3a71-46de-beee-791468607b75/r

See our lesson on Prompt Chaining here.

https://smith.langchain.com/public/332fa4fc-b6ca-416e-baa3-161625e69163/r

With parallelization, LLMs work simultaneously on a task:

LLMs can sometimes work simultaneously on a task and have their outputs aggregated programmatically. This workflow, parallelization, manifests in two key variations: Sectioning: Breaking a task into independent subtasks run in parallel. Voting: Running the same task multiple times to get diverse outputs.

When to use this workflow: Parallelization is effective when the divided subtasks can be parallelized for speed, or when multiple perspectives or attempts are needed for higher confidence results. For complex tasks with multiple considerations, LLMs generally perform better when each consideration is handled by a separate LLM call, allowing focused attention on each specific aspect.

https://smith.langchain.com/public/3be2e53c-ca94-40dd-934f-82ff87fac277/r

See our documentation on parallelization here.

See our lesson on parallelization here.

https://smith.langchain.com/public/623d033f-e814-41e9-80b1-75e6abb67801/r

Routing classifies an input and directs it to a followup task. As noted in the Anthropic blog on Building Effective Agents:

Routing classifies an input and directs it to a specialized followup task. This workflow allows for separation of concerns, and building more specialized prompts. Without this workflow, optimizing for one kind of input can hurt performance on other inputs.

When to use this workflow: Routing works well for complex tasks where there are distinct categories that are better handled separately, and where classification can be handled accurately, either by an LLM or a more traditional classification model/algorithm.

https://smith.langchain.com/public/c4580b74-fe91-47e4-96fe-7fac598d509c/r

See our lesson on routing here.

Here is RAG workflow that routes questions. See our video here.

https://smith.langchain.com/public/5e2eb979-82dd-402c-b1a0-a8cceaf2a28a/r

With orchestrator-worker, an orchestrator breaks down a task and delegates each sub-task to workers. As noted in the Anthropic blog on Building Effective Agents:

In the orchestrator-workers workflow, a central LLM dynamically breaks down tasks, delegates them to worker LLMs, and synthesizes their results.

When to use this workflow: This workflow is well-suited for complex tasks where you can't predict the subtasks needed (in coding, for example, the number of files that need to be changed and the nature of the change in each file likely depend on the task). Whereas it's topographically similar, the key difference from parallelization is its flexibility—subtasks aren't pre-defined, but determined by the orchestrator based on the specific input.

Creating Workers in LangGraph

Because orchestrator-worker workflows are common, LangGraph has the Send API to support this. It lets you dynamically create worker nodes and send each one a specific input. Each worker has its own state, and all worker outputs are written to a shared state key that is accessible to the orchestrator graph. This gives the orchestrator access to all worker output and allows it to synthesize them into a final output. As you can see below, we iterate over a list of sections and Send each to a worker node. See further documentation here and here.

https://smith.langchain.com/public/78cbcfc3-38bf-471d-b62a-b299b144237d/r

See our lesson on orchestrator-worker here.

Here is a project that uses orchestrator-worker for report planning and writing. See our video here.

https://smith.langchain.com/public/75a636d0-6179-4a12-9836-e0aa571e87c5/r

In the evaluator-optimizer workflow, one LLM call generates a response while another provides evaluation and feedback in a loop:

When to use this workflow: This workflow is particularly effective when we have clear evaluation criteria, and when iterative refinement provides measurable value. The two signs of good fit are, first, that LLM responses can be demonstrably improved when a human articulates their feedback; and second, that the LLM can provide such feedback. This is analogous to the iterative writing process a human writer might go through when producing a polished document.

https://smith.langchain.com/public/86ab3e60-2000-4bff-b988-9b89a3269789/r

Here is an assistant that uses evaluator-optimizer to improve a report. See our video here.

Here is a RAG workflow that grades answers for hallucinations or errors. See our video here.

https://smith.langchain.com/public/f66830be-4339-4a6b-8a93-389ce5ae27b4/r

Agents are typically implemented as an LLM performing actions (via tool-calling) based on environmental feedback in a loop. As noted in the Anthropic blog on Building Effective Agents:

Agents can handle sophisticated tasks, but their implementation is often straightforward. They are typically just LLMs using tools based on environmental feedback in a loop. It is therefore crucial to design toolsets and their documentation clearly and thoughtfully.

When to use agents: Agents can be used for open-ended problems where it's difficult or impossible to predict the required number of steps, and where you can't hardcode a fixed path. The LLM will potentially operate for many turns, and you must have some level of trust in its decision-making. Agents' autonomy makes them ideal for scaling tasks in trusted environments.

https://smith.langchain.com/public/051f0391-6761-4f8c-a53b-22231b016690/r

See our lesson on agents here.

Here is a project that uses a tool calling agent to create / store long-term memories.

https://smith.langchain.com/public/42ae8bf9-3935-4504-a081-8ddbcbfc8b2e/r

LangGraph also provides a pre-built method for creating an agent as defined above (using the create_react_agent function):

https://langchain-ai.github.io/langgraph/how-tos/create-react-agent/

API Reference: create_react_agent

https://smith.langchain.com/public/abab6a44-29f6-4b97-8164-af77413e494d/r

By constructing each of the above in LangGraph, we get a few things:

LangGraph persistence layer supports interruption and approval of actions (e.g., Human In The Loop). See Module 3 of LangChain Academy.

LangGraph persistence layer supports conversational (short-term) memory and long-term memory. See Modules 2 and 5 of LangChain Academy:

LangGraph provides several ways to stream workflow / agent outputs or intermediate state. See Module 3 of LangChain Academy.

LangGraph provides an easy on-ramp for deployment, observability, and evaluation. See module 6 of LangChain Academy.

**Examples:**

Example 1 (unknown):
```unknown
pip install langchain_core langchain-anthropic langgraph
```

Example 2 (python):
```python
import os
import getpass

from langchain_anthropic import ChatAnthropic

def _set_env(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"{var}: ")


_set_env("ANTHROPIC_API_KEY")

llm = ChatAnthropic(model="claude-3-5-sonnet-latest")
```

Example 3 (python):
```python
# Schema for structured output
from pydantic import BaseModel, Field

class SearchQuery(BaseModel):
    search_query: str = Field(None, description="Query that is optimized web search.")
    justification: str = Field(
        None, description="Why this query is relevant to the user's request."
    )


# Augment the LLM with schema for structured output
structured_llm = llm.with_structured_output(SearchQuery)

# Invoke the augmented LLM
output = structured_llm.invoke("How does Calcium CT score relate to high cholesterol?")

# Define a tool
def multiply(a: int, b: int) -> int:
    return a * b

# Augment the LLM with tools
llm_with_tools = llm.bind_tools([multiply])

# Invoke the LLM with input that triggers the tool call
msg = llm_with_tools.invoke("What is 2 times 3?")

# Get the tool call
msg.tool_calls
```

Example 4 (python):
```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from IPython.display import Image, display


# Graph state
class State(TypedDict):
    topic: str
    joke: str
    improved_joke: str
    final_joke: str


# Nodes
def generate_joke(state: State):
    """First LLM call to generate initial joke"""

    msg = llm.invoke(f"Write a short joke about {state['topic']}")
    return {"joke": msg.content}


def check_punchline(state: State):
    """Gate function to check if the joke has a punchline"""

    # Simple check - does the joke contain "?" or "!"
    if "?" in state["joke"] or "!" in state["joke"]:
        return "Pass"
    return "Fail"


def improve_joke(state: State):
    """Second LLM call to improve the joke"""

    msg = llm.invoke(f"Make this joke funnier by adding wordplay: {state['joke']}")
    return {"improved_joke": msg.content}


def polish_joke(state: State):
    """Third LLM call for final polish"""

    msg = llm.invoke(f"Add a surprising twist to this joke: {state['improved_joke']}")
    return {"final_joke": msg.content}


# Build workflow
workflow = StateGraph(State)

# Add nodes
workflow.add_node("generate_joke", generate_joke)
workflow.add_node("improve_joke", improve_joke)
workflow.add_node("polish_joke", polish_joke)

# Add edges to connect nodes
workflow.add_edge(START, "generate_joke")
workflow.add_conditional_edges(
    "generate_joke", check_punchline, {"Fail": "improve_joke", "Pass": END}
)
workflow.add_edge("improve_joke", "polish_joke")
workflow.add_edge("polish_joke", END)

# Compile
chain = workflow.compile()

# Show workflow
display(Image(chain.get_graph().draw_mermaid_png()))

# Invoke
state = chain.invoke({"topic": "cats"})
print("Initial joke:")
print(state["joke"])
print("\n--- --- ---\n")
if "improved_joke" in state:
    print("Improved joke:")
    print(state["improved_joke"])
    print("\n--- --- ---\n")

    print("Final joke:")
    print(state["final_joke"])
else:
    print("Joke failed quality gate - no punchline detected!")
```

---

## Use subgraphs¶

**URL:** https://langchain-ai.github.io/langgraph/how-tos/subgraph/

**Contents:**
- Use subgraphs¶
- Setup¶
- Shared state schemas¶
- Different state schemas¶
- Add persistence¶
- View subgraph state¶
- Stream subgraph outputs¶

This guide explains the mechanics of using subgraphs. A common application of subgraphs is to build multi-agent systems.

When adding subgraphs, you need to define how the parent graph and the subgraph communicate:

Set up LangSmith for LangGraph development

Sign up for LangSmith to quickly spot issues and improve the performance of your LangGraph projects. LangSmith lets you use trace data to debug, test, and monitor your LLM apps built with LangGraph — read more about how to get started here.

A common case is for the parent graph and subgraph to communicate over a shared state key (channel) in the schema. For example, in multi-agent systems, the agents often communicate over a shared messages key.

If your subgraph shares state keys with the parent graph, you can follow these steps to add it to your graph:

API Reference: StateGraph

For more complex systems you might want to define subgraphs that have a completely different schema from the parent graph (no shared keys). For example, you might want to keep a private message history for each of the agents in a multi-agent system.

If that's the case for your application, you need to define a node function that invokes the subgraph. This function needs to transform the input (parent) state to the subgraph state before invoking the subgraph, and transform the results back to the parent state before returning the state update from the node.

API Reference: StateGraph

This is an example with two levels of subgraphs: parent -> child -> grandchild.

You only need to provide the checkpointer when compiling the parent graph. LangGraph will automatically propagate the checkpointer to the child subgraphs.

API Reference: START | StateGraph | MemorySaver

If you want the subgraph to have its own memory, you can compile it with the appropriate checkpointer option. This is useful in multi-agent systems, if you want agents to keep track of their internal message histories:

When you enable persistence, you can inspect the graph state (checkpoint) via the appropriate method. To view the subgraph state, you can use the subgraphs option.

You can inspect the graph state via graph.get_state(config). To view the subgraph state, you can use graph.get_state(config, subgraphs=True).

Available only when interrupted

Subgraph state can only be viewed when the subgraph is interrupted. Once you resume the graph, you won't be able to access the subgraph state.

To include outputs from subgraphs in the streamed outputs, you can set the subgraphs option in the stream method of the parent graph. This will stream outputs from both the parent graph and any subgraphs.

**Examples:**

Example 1 (unknown):
```unknown
pip install -U langgraph
```

Example 2 (python):
```python
from typing_extensions import TypedDict
from langgraph.graph.state import StateGraph, START

class State(TypedDict):
    foo: str

# Subgraph

def subgraph_node_1(state: State):
    return {"foo": "hi! " + state["foo"]}

subgraph_builder = StateGraph(State)
subgraph_builder.add_node(subgraph_node_1)
subgraph_builder.add_edge(START, "subgraph_node_1")
subgraph = subgraph_builder.compile()

# Parent graph

builder = StateGraph(State)
builder.add_node("node_1", subgraph)
builder.add_edge(START, "node_1")
graph = builder.compile()
```

Example 3 (python):
```python
from typing_extensions import TypedDict
from langgraph.graph.state import StateGraph, START

# Define subgraph
class SubgraphState(TypedDict):
    foo: str  # (1)! 
    bar: str  # (2)!

def subgraph_node_1(state: SubgraphState):
    return {"bar": "bar"}

def subgraph_node_2(state: SubgraphState):
    # note that this node is using a state key ('bar') that is only available in the subgraph
    # and is sending update on the shared state key ('foo')
    return {"foo": state["foo"] + state["bar"]}

subgraph_builder = StateGraph(SubgraphState)
subgraph_builder.add_node(subgraph_node_1)
subgraph_builder.add_node(subgraph_node_2)
subgraph_builder.add_edge(START, "subgraph_node_1")
subgraph_builder.add_edge("subgraph_node_1", "subgraph_node_2")
subgraph = subgraph_builder.compile()

# Define parent graph
class ParentState(TypedDict):
    foo: str

def node_1(state: ParentState):
    return {"foo": "hi! " + state["foo"]}

builder = StateGraph(ParentState)
builder.add_node("node_1", node_1)
builder.add_node("node_2", subgraph)
builder.add_edge(START, "node_1")
builder.add_edge("node_1", "node_2")
graph = builder.compile()

for chunk in graph.stream({"foo": "foo"}):
    print(chunk)
```

Example 4 (unknown):
```unknown
{'node_1': {'foo': 'hi! foo'}}
{'node_2': {'foo': 'hi! foobar'}}
```

---

## Add tools¶

**URL:** https://langchain-ai.github.io/langgraph/tutorials/get-started/2-add-tools/

**Contents:**
- Add tools¶
- Prerequisites¶
- 1. Install the search engine¶
- 2. Configure your environment¶
- 3. Define the tool¶
- 4. Define the graph¶
- 5. Create a function to run the tools¶
- 6. Define the conditional_edges¶
- 7. Visualize the graph (optional)¶
- 8. Ask the bot questions¶

To handle queries that your chatbot can't answer "from memory", integrate a web search tool. The chatbot can use this tool to find relevant information and provide better responses.

This tutorial builds on Build a basic chatbot.

Before you start this tutorial, ensure you have the following:

Install the requirements to use the Tavily Search Engine:

Configure your environment with your search engine API key:

Define the web search tool:

API Reference: TavilySearch

The results are page summaries our chat bot can use to answer questions:

For the StateGraph you created in the first tutorial, add bind_tools on the LLM. This lets the LLM know the correct JSON format to use if it wants to use the search engine.

Let's first select our LLM:

pip install -U "langchain[openai]" import os from langchain.chat_models import init_chat_model os.environ["OPENAI_API_KEY"] = "sk-..." llm = init_chat_model("openai:gpt-4.1")

👉 Read the OpenAI integration docs

pip install -U "langchain[anthropic]" import os from langchain.chat_models import init_chat_model os.environ["ANTHROPIC_API_KEY"] = "sk-..." llm = init_chat_model("anthropic:claude-3-5-sonnet-latest")

👉 Read the Anthropic integration docs

pip install -U "langchain[openai]" import os from langchain.chat_models import init_chat_model os.environ["AZURE_OPENAI_API_KEY"] = "..." os.environ["AZURE_OPENAI_ENDPOINT"] = "..." os.environ["OPENAI_API_VERSION"] = "2025-03-01-preview" llm = init_chat_model( "azure_openai:gpt-4.1", azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"], )

👉 Read the Azure integration docs

pip install -U "langchain[google-genai]" import os from langchain.chat_models import init_chat_model os.environ["GOOGLE_API_KEY"] = "..." llm = init_chat_model("google_genai:gemini-2.0-flash")

👉 Read the Google GenAI integration docs

pip install -U "langchain[aws]" from langchain.chat_models import init_chat_model # Follow the steps here to configure your credentials: # https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html llm = init_chat_model( "anthropic.claude-3-5-sonnet-20240620-v1:0", model_provider="bedrock_converse", )

👉 Read the AWS Bedrock integration docs

We can now incorporate it into a StateGraph:

API Reference: StateGraph | START | END | add_messages

Now, create a function to run the tools if they are called. Do this by adding the tools to a new node called BasicToolNode that checks the most recent message in the state and calls tools if the message contains tool_calls. It relies on the LLM's tool_calling support, which is available in Anthropic, OpenAI, Google Gemini, and a number of other LLM providers.

API Reference: ToolMessage

If you do not want to build this yourself in the future, you can use LangGraph's prebuilt ToolNode.

With the tool node added, now you can define the conditional_edges.

Edges route the control flow from one node to the next. Conditional edges start from a single node and usually contain "if" statements to route to different nodes depending on the current graph state. These functions receive the current graph state and return a string or list of strings indicating which node(s) to call next.

Next, define a router function called route_tools that checks for tool_calls in the chatbot's output. Provide this function to the graph by calling add_conditional_edges, which tells the graph that whenever the chatbot node completes to check this function to see where to go next.

The condition will route to tools if tool calls are present and END if not. Because the condition can return END, you do not need to explicitly set a finish_point this time.

You can replace this with the prebuilt tools_condition to be more concise.

You can visualize the graph using the get_graph method and one of the "draw" methods, like draw_ascii or draw_png. The draw methods each require additional dependencies.

Now you can ask the chatbot questions outside its training data:

For ease of use, adjust your code to replace the following with LangGraph prebuilt components. These have built in functionality like parallel API execution.

pip install -U "langchain[openai]" import os from langchain.chat_models import init_chat_model os.environ["OPENAI_API_KEY"] = "sk-..." llm = init_chat_model("openai:gpt-4.1")

👉 Read the OpenAI integration docs

pip install -U "langchain[anthropic]" import os from langchain.chat_models import init_chat_model os.environ["ANTHROPIC_API_KEY"] = "sk-..." llm = init_chat_model("anthropic:claude-3-5-sonnet-latest")

👉 Read the Anthropic integration docs

pip install -U "langchain[openai]" import os from langchain.chat_models import init_chat_model os.environ["AZURE_OPENAI_API_KEY"] = "..." os.environ["AZURE_OPENAI_ENDPOINT"] = "..." os.environ["OPENAI_API_VERSION"] = "2025-03-01-preview" llm = init_chat_model( "azure_openai:gpt-4.1", azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"], )

👉 Read the Azure integration docs

pip install -U "langchain[google-genai]" import os from langchain.chat_models import init_chat_model os.environ["GOOGLE_API_KEY"] = "..." llm = init_chat_model("google_genai:gemini-2.0-flash")

👉 Read the Google GenAI integration docs

pip install -U "langchain[aws]" from langchain.chat_models import init_chat_model # Follow the steps here to configure your credentials: # https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html llm = init_chat_model( "anthropic.claude-3-5-sonnet-20240620-v1:0", model_provider="bedrock_converse", )

👉 Read the AWS Bedrock integration docs

Congratulations! You've created a conversational agent in LangGraph that can use a search engine to retrieve updated information when needed. Now it can handle a wider range of user queries.

To inspect all the steps your agent just took, check out this LangSmith trace.

The chatbot cannot remember past interactions on its own, which limits its ability to have coherent, multi-turn conversations. In the next part, you will add memory to address this.

**Examples:**

Example 1 (unknown):
```unknown
pip install -U langchain-tavily
```

Example 2 (unknown):
```unknown
import os

os.environ["TAVILY_API_KEY"] = "tvly-..."
```

Example 3 (python):
```python
from langchain_tavily import TavilySearch

tool = TavilySearch(max_results=2)
tools = [tool]
tool.invoke("What's a 'node' in LangGraph?")
```

Example 4 (python):
```python
{'query': "What's a 'node' in LangGraph?",
'follow_up_questions': None,
'answer': None,
'images': [],
'results': [{'title': "Introduction to LangGraph: A Beginner's Guide - Medium",
'url': 'https://medium.com/@cplog/introduction-to-langgraph-a-beginners-guide-14f9be027141',
'content': 'Stateful Graph: LangGraph revolves around the concept of a stateful graph, where each node in the graph represents a step in your computation, and the graph maintains a state that is passed around and updated as the computation progresses. LangGraph supports conditional edges, allowing you to dynamically determine the next node to execute based on the current state of the graph. We define nodes for classifying the input, handling greetings, and handling search queries. def classify_input_node(state): LangGraph is a versatile tool for building complex, stateful applications with LLMs. By understanding its core concepts and working through simple examples, beginners can start to leverage its power for their projects. Remember to pay attention to state management, conditional edges, and ensuring there are no dead-end nodes in your graph.',
'score': 0.7065353,
'raw_content': None},
{'title': 'LangGraph Tutorial: What Is LangGraph and How to Use It?',
'url': 'https://www.datacamp.com/tutorial/langgraph-tutorial',
'content': 'LangGraph is a library within the LangChain ecosystem that provides a framework for defining, coordinating, and executing multiple LLM agents (or chains) in a structured and efficient manner. By managing the flow of data and the sequence of operations, LangGraph allows developers to focus on the high-level logic of their applications rather than the intricacies of agent coordination. Whether you need a chatbot that can handle various types of user requests or a multi-agent system that performs complex tasks, LangGraph provides the tools to build exactly what you need. LangGraph significantly simplifies the development of complex LLM applications by providing a structured framework for managing state and coordinating agent interactions.',
'score': 0.5008063,
'raw_content': None}],
'response_time': 1.38}
```

---

## Call tools¶

**URL:** https://langchain-ai.github.io/langgraph/how-tos/tool-calling/

**Contents:**
- Call tools¶
- Define a tool¶
- Run a tool¶
- Use in an agent¶
  - Dynamically select tools¶
- Use in a workflow¶
    - ToolNode¶
- Tool customization¶
  - Parameter descriptions¶
  - Explicit input schema¶

Tools encapsulate a callable function and its input schema. These can be passed to compatible chat models, allowing the model to decide whether to invoke a tool and determine the appropriate arguments.

You can define your own tools or use prebuilt tools

Define a basic tool with the @tool decorator:

Tools conform to the Runnable interface, which means you can run a tool using the invoke method:

If the tool is invoked with type="tool_call", it will return a ToolMessage:

To create a tool-calling agent, you can use the prebuilt create_react_agent:

API Reference: tool | create_react_agent

Configure tool availability at runtime based on context:

API Reference: init_chat_model | tool | create_react_agent | AgentState

Added in version 0.6.0

If you are writing a custom workflow, you will need to:

Use model.bind_tools() to register the tools with the model.

API Reference: init_chat_model

LLMs automatically determine if a tool invocation is necessary and handle calling the tool with the appropriate arguments.

To execute tools in custom workflows, use the prebuilt ToolNode or implement your own custom node.

ToolNode is a specialized node for executing tools in a workflow. It provides the following features:

ToolNode operates on MessagesState:

API Reference: ToolNode

This is an example of creating a tool-calling agent from scratch using ToolNode. You can also use LangGraph's prebuilt agent.

For more control over tool behavior, use the @tool decorator.

Auto-generate descriptions from docstrings:

Define schemas using args_schema:

Override the default tool name using the first argument or name property:

Tools within LangGraph sometimes require context data, such as runtime-only arguments (e.g., user IDs or session details), that should not be controlled by the model. LangGraph provides three methods for managing such context:

Use configuration when you have immutable runtime data that tools require, such as user identifiers. You pass these arguments via RunnableConfig at invocation and access them in the tool:

API Reference: tool | RunnableConfig

Short-term memory maintains dynamic state that changes during a single execution.

To access (read) the graph state inside the tools, you can use a special parameter annotation — InjectedState:

API Reference: tool | InjectedState | create_react_agent | AgentState

Use a tool that returns a Command to update user_name and append a confirmation message:

API Reference: Command | ToolMessage | tool | InjectedToolCallId

If you want to use tools that return Command and update graph state, you can either use prebuilt create_react_agent / ToolNode components, or implement your own tool-executing node that collects Command objects returned by the tools and returns a list of them, e.g.:

Use long-term memory to store user-specific or application-specific data across conversations. This is useful for applications like chatbots, where you want to remember user preferences or other information.

To use long-term memory, you need to:

To access information in the store:

API Reference: RunnableConfig | tool | StateGraph | get_store

To update information in the store:

API Reference: RunnableConfig | tool | StateGraph | get_store

Use return_direct=True to immediately return a tool's result without executing additional logic.

This is useful for tools that should not trigger further processing or tool calls, allowing you to return results directly to the user.

Using without prebuilt components

If you are building a custom workflow and are not relying on create_react_agent or ToolNode, you will also need to implement the control flow to handle return_direct=True.

If you need to force a specific tool to be used, you will need to configure this at the model level using the tool_choice parameter in the bind_tools method.

Force specific tool usage via tool_choice:

To force the agent to use specific tools, you can set the tool_choice option in model.bind_tools():

Forcing tool usage without stopping conditions can create infinite loops. Use one of the following safeguards:

Tool choice configuration

The tool_choice parameter is used to configure which tool should be used by the model when it decides to call a tool. This is useful when you want to ensure that a specific tool is always called for a particular task or when you want to override the model's default behavior of choosing a tool based on its internal logic.

Note that not all models support this feature, and the exact configuration may vary depending on the model you are using.

For supported providers, you can disable parallel tool calling by setting parallel_tool_calls=False via the model.bind_tools() method:

LangGraph provides built-in error handling for tool execution through the prebuilt ToolNode component, used both independently and in prebuilt agents.

By default, ToolNode catches exceptions raised during tool execution and returns them as ToolMessage objects with a status indicating an error.

API Reference: AIMessage | ToolNode

To propagate exceptions directly, disable error handling:

With error handling disabled, exceptions raised by tools will propagate up, requiring explicit management.

Provide a custom error message by setting the error handling parameter to a string:

Error handling in prebuilt agents (create_react_agent) leverages ToolNode:

API Reference: create_react_agent

To disable or customize error handling in prebuilt agents, explicitly pass a configured ToolNode:

As the number of available tools grows, you may want to limit the scope of the LLM's selection, to decrease token consumption and to help manage sources of error in LLM reasoning.

To address this, you can dynamically adjust the tools available to a model by retrieving relevant tools at runtime using semantic search.

See langgraph-bigtool prebuilt library for a ready-to-use implementation.

You can use prebuilt tools from model providers by passing a dictionary with tool specs to the tools parameter of create_react_agent. For example, to use the web_search_preview tool from OpenAI:

API Reference: create_react_agent

Please consult the documentation for the specific model you are using to see which tools are available and how to use them.

Additionally, LangChain supports a wide range of prebuilt tool integrations for interacting with APIs, databases, file systems, web data, and more. These tools extend the functionality of agents and enable rapid development.

You can browse the full list of available integrations in the LangChain integrations directory.

Some commonly used tool categories include:

These integrations can be configured and added to your agents using the same tools parameter shown in the examples above.

**Examples:**

Example 1 (python):
```python
from langchain_core.tools import tool

@tool
def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b
```

Example 2 (unknown):
```unknown
multiply.invoke({"a": 6, "b": 7})  # returns 42
```

Example 3 (unknown):
```unknown
tool_call = {
    "type": "tool_call",
    "id": "1",
    "args": {"a": 42, "b": 7}
}
multiply.invoke(tool_call) # returns a ToolMessage object
```

Example 4 (unknown):
```unknown
ToolMessage(content='294', name='multiply', tool_call_id='1')
```

---

## Multi-agent supervisor¶

**URL:** https://langchain-ai.github.io/langgraph/tutorials/multi_agent/agent_supervisor

**Contents:**
- Multi-agent supervisor¶
- Setup¶
- 1. Create worker agents¶
  - Research agent¶
  - Math agent¶
- 2. Create supervisor with langgraph-supervisor¶
- 3. Create supervisor from scratch¶
  - Set up agent communication¶
  - Create supervisor agent¶
  - Create multi-agent graph¶

Supervisor is a multi-agent architecture where specialized agents are coordinated by a central supervisor agent. The supervisor agent controls all communication flow and task delegation, making decisions about which agent to invoke based on the current context and task requirements.

In this tutorial, you will build a supervisor system with two agents — a research and a math expert. By the end of the tutorial you will:

First, let's install required packages and set our API keys

Sign up for LangSmith to quickly spot issues and improve the performance of your LangGraph projects. LangSmith lets you use trace data to debug, test, and monitor your LLM apps built with LangGraph.

First, let's create our specialized worker agents — research agent and math agent:

For web search, we will use TavilySearch tool from langchain-tavily:

API Reference: TavilySearch

Output: Find events, attractions, deals, and more at nyctourism.com Skip Main Navigation Menu The Official Website of the City of New York Text Size Powered by Translate SearchSearch Primary Navigation The official website of NYC Home NYC Resources NYC311 Office of the Mayor Events Connect Jobs Search Office of the Mayor | Mayor's Bio | City of New York Secondary Navigation MayorBiographyNewsOfficials Eric L. Adams 110th Mayor of New York City Mayor Eric Adams has served the people of New York City as an NYPD officer, State Senator, Brooklyn Borough President, and now as the 110th Mayor of the City of New York. Mayor Eric Adams has served the people of New York City as an NYPD officer, State Senator, Brooklyn Borough President, and now as the 110th Mayor of the City of New York. He gave voice to a diverse coalition of working families in all five boroughs and is leading the fight to bring back New York City's economy, reduce inequality, improve public safety, and build a stronger, healthier city that delivers for all New Yorkers. As the representative of one of the nation's largest counties, Eric fought tirelessly to grow the local economy, invest in schools, reduce inequality, improve public safety, and advocate for smart policies and better government that delivers for all New Yorkers.

To create individual worker agents, we will use LangGraph's prebuilt agent.

API Reference: create_react_agent

Let's run the agent to verify that it behaves as expected.

We'll use pretty_print_messages helper to render the streamed agent outputs nicely

Output: Update from node agent: ================================== Ai Message ================================== Name: research_agent Tool Calls: tavily_search (call_U748rQhQXT36sjhbkYLSXQtJ) Call ID: call_U748rQhQXT36sjhbkYLSXQtJ Args: query: current mayor of New York City search_depth: basic Update from node tools: ================================= Tool Message ================================== Name: tavily_search {"query": "current mayor of New York City", "follow_up_questions": null, "answer": null, "images": [], "results": [{"title": "List of mayors of New York City - Wikipedia", "url": "https://en.wikipedia.org/wiki/List_of_mayors_of_New_York_City", "content": "The mayor of New York City is the chief executive of the Government of New York City, as stipulated by New York City's charter.The current officeholder, the 110th in the sequence of regular mayors, is Eric Adams, a member of the Democratic Party.. During the Dutch colonial period from 1624 to 1664, New Amsterdam was governed by the Director of Netherland.", "score": 0.9039154, "raw_content": null}, {"title": "Office of the Mayor | Mayor's Bio | City of New York - NYC.gov", "url": "https://www.nyc.gov/office-of-the-mayor/bio.page", "content": "Mayor Eric Adams has served the people of New York City as an NYPD officer, State Senator, Brooklyn Borough President, and now as the 110th Mayor of the City of New York. He gave voice to a diverse coalition of working families in all five boroughs and is leading the fight to bring back New York City's economy, reduce inequality, improve", "score": 0.8405867, "raw_content": null}, {"title": "Eric Adams - Wikipedia", "url": "https://en.wikipedia.org/wiki/Eric_Adams", "content": "Eric Leroy Adams (born September 1, 1960) is an American politician and former police officer who has served as the 110th mayor of New York City since 2022. Adams was an officer in the New York City Transit Police and then the New York City Police Department (```

For math agent tools we will use vanilla Python functions:

Let's run the math agent:

Output: Update from node agent: ================================== Ai Message ================================== Name: math_agent Tool Calls: add (call_p6OVLDHB4LyCNCxPOZzWR15v) Call ID: call_p6OVLDHB4LyCNCxPOZzWR15v Args: a: 3 b: 5 Update from node tools: ================================= Tool Message ================================== Name: add 8.0 Update from node agent: ================================== Ai Message ================================== Name: math_agent Tool Calls: multiply (call_EoaWHMLFZAX4AkajQCtZvbli) Call ID: call_EoaWHMLFZAX4AkajQCtZvbli Args: a: 8 b: 7 Update from node tools: ================================= Tool Message ================================== Name: multiply 56.0 Update from node agent: ================================== Ai Message ================================== Name: math_agent 56

To implement out multi-agent system, we will use create_supervisor from the prebuilt langgraph-supervisor library:

API Reference: create_supervisor | init_chat_model

Note: When you run this code, it will generate and display a visual representation of the supervisor graph showing the flow between the supervisor and worker agents.

Let's now run it with a query that requires both agents:

Output: Update from node supervisor: ================================= Tool Message ================================== Name: transfer_to_research_agent Successfully transferred to research_agent Update from node research_agent: ================================= Tool Message ================================== Name: transfer_back_to_supervisor Successfully transferred back to supervisor Update from node supervisor: ================================= Tool Message ================================== Name: transfer_to_math_agent Successfully transferred to math_agent Update from node math_agent: ================================= Tool Message ================================== Name: transfer_back_to_supervisor Successfully transferred back to supervisor Update from node supervisor: ================================== Ai Message ================================== Name: supervisor In 2024, the US GDP was $29.18 trillion and New York State's GDP was $2.297 trillion. New York State accounted for approximately 7.87% of the total US GDP in 2024.

Let's now implement this same multi-agent system from scratch. We will need to:

We will need to define a way for the supervisor agent to communicate with the worker agents. A common way to implement this in multi-agent architectures is using handoffs, where one agent hands off control to another. Handoffs allow you to specify:

We will implement handoffs via handoff tools and give these tools to the supervisor agent: when the supervisor calls these tools, it will hand off control to a worker agent, passing the full message history to that agent.

API Reference: tool | InjectedToolCallId | InjectedState | StateGraph | START | Command

Then, let's create the supervisor agent with the handoff tools we just defined. We will use the prebuilt create_react_agent:

Putting this all together, let's create a graph for our overall multi-agent system. We will add the supervisor and the individual agents as subgraph nodes.

Notice that we've added explicit edges from worker agents back to the supervisor — this means that they are guaranteed to return control back to the supervisor. If you want the agents to respond directly to the user (i.e., turn the system into a router, you can remove these edges).

Note: When you run this code, it will generate and display a visual representation of the multi-agent supervisor graph showing the flow between the supervisor and worker agents.

With the multi-agent graph created, let's now run it!

Output: Update from node supervisor: ================================= Tool Message ================================== Name: transfer_to_research_agent Successfully transferred to research_agent Update from node research_agent: ================================== Ai Message ================================== Name: research_agent - US GDP in 2024 is projected to be about $28.18 trillion USD (Statista; CBO projection). - New York State's nominal GDP for 2024 is estimated at approximately $2.16 trillion USD (various economic reports). - New York State's share of US GDP in 2024 is roughly 7.7%. Sources: - https://www.statista.com/statistics/216985/forecast-of-us-gross-domestic-product/ - https://nyassembly.gov/Reports/WAM/2025economic_revenue/2025_report.pdf?v=1740533306 Update from node supervisor: ================================= Tool Message ================================== Name: transfer_to_math_agent Successfully transferred to math_agent Update from node math_agent: ================================== Ai Message ================================== Name: math_agent US GDP in 2024: $28.18 trillion New York State GDP in 2024: $2.16 trillion Percentage of US GDP from New York State: 7.67% Update from node supervisor: ================================== Ai Message ================================== Name: supervisor Here are your results: - 2024 US GDP (projected): $28.18 trillion USD - 2024 New York State GDP (estimated): $2.16 trillion USD - New York State's share of US GDP: approximately 7.7% If you need the calculation steps or sources, let me know!

Let's examine the full resulting message history:

Output: ================================ Human Message ================================== find US and New York state GDP in 2024. what % of US GDP was New York state? ================================== Ai Message =================================== Name: supervisor Tool Calls: transfer_to_research_agent (call_KlGgvF5ahlAbjX8d2kHFjsC3) Call ID: call_KlGgvF5ahlAbjX8d2kHFjsC3 Args: ================================= Tool Message ================================== Name: transfer_to_research_agent Successfully transferred to research_agent ================================== Ai Message =================================== Name: research_agent Tool Calls: tavily_search (call_ZOaTVUA6DKrOjWQldLhtrsO2) Call ID: call_ZOaTVUA6DKrOjWQldLhtrsO2 Args: query: US GDP 2024 estimate or actual search_depth: advanced tavily_search (call_QsRAasxW9K03lTlqjuhNLFbZ) Call ID: call_QsRAasxW9K03lTlqjuhNLFbZ Args: query: New York state GDP 2024 estimate or actual search_depth: advanced ================================= Tool Message ================================== Name: tavily_search {"query": "US GDP 2024 estimate or actual", "follow_up_questions": null, "answer": null, "images": [], "results": [{"url": "https://www.advisorperspectives.com/dshort/updates/2025/05/29/gdp-gross-domestic-product-q1-2025-second-estimate", "title": "Q1 GDP Second Estimate: Real GDP at -0.2%, Higher Than Expected", "content": "> Real gross domestic product (GDP) decreased at an annual rate of 0.2 percent in the first quarter of 2025 (January, February, and March), according to the second estimate released by the U.S. Bureau of Economic Analysis. In the fourth quarter of 2024, real GDP increased 2.4 percent. The decrease in real GDP in the first quarter primarily reflected an increase in imports, which are a subtraction in the calculation of GDP, and a decrease in government spending. These movements were partly [...] by [Harry Mamaysky](https://www.advisor```

You can see that the supervisor system appends all of the individual agent messages (i.e., their internal tool-calling loop) to the full message history. This means that on every supervisor turn, supervisor agent sees this full history. If you want more control over:

how agent outputs are added: you can control how much of the agent's internal message history is added to the overall supervisor message history by wrapping the agent in a separate node function:

So far the individual agents relied on interpreting full message history to determine their tasks. An alternative approach is to ask the supervisor to formulate a task explicitly. We can do so by adding a task_description parameter to the handoff_tool function.

We're using Send() primitive in the handoff_tool. This means that instead of receiving the full supervisor graph state as input, each worker agent only sees the contents of the Send payload. In this example, we're sending the task description as a single "human" message.

Let's now running it with the same input query:

Output: Update from subgraph supervisor: Update from node agent: ================================== Ai Message ================================== Name: supervisor Tool Calls: transfer_to_research_agent (call_tk8q8py8qK6MQz6Kj6mijKua) Call ID: call_tk8q8py8qK6MQz6Kj6mijKua Args: task_description: Find the 2024 GDP (Gross Domestic Product) for both the United States and New York state, using the most up-to-date and reputable sources available. Provide both GDP values and cite the data sources. Update from subgraph research_agent: Update from node agent: ================================== Ai Message ================================== Name: research_agent Tool Calls: tavily_search (call_KqvhSvOIhAvXNsT6BOwbPlRB) Call ID: call_KqvhSvOIhAvXNsT6BOwbPlRB Args: query: 2024 United States GDP value from a reputable source search_depth: advanced tavily_search (call_kbbAWBc9KwCWKHmM5v04H88t) Call ID: call_kbbAWBc9KwCWKHmM5v04H88t Args: query: 2024 New York state GDP value from a reputable source search_depth: advanced Update from subgraph research_agent: Update from node tools: ================================= Tool Message ================================== Name: tavily_search {"query": "2024 United States GDP value from a reputable source", "follow_up_questions": null, "answer": null, "images": [], "results": [{"url": "https://www.focus-economics.com/countries/united-states/", "title": "United States Economy Overview - Focus Economics", "content": "The United States' Macroeconomic Analysis:\n------------------------------------------\n\n**Nominal GDP of USD 29,185 billion in 2024.**\n\n**Nominal GDP of USD 29,179 billion in 2024.**\n\n**GDP per capita of USD 86,635 compared to the global average of USD 10,589.**\n\n**GDP per capita of USD 86,652 compared to the global average of USD 10,589.**\n\n**Average real GDP growth of 2.5% over the last decade.**\n\n**Average real GDP growth of ```

**Examples:**

Example 1 (unknown):
```unknown
%%capture --no-stderr
%pip install -U langgraph langgraph-supervisor langchain-tavily "langchain[openai]"
```

Example 2 (python):
```python
import getpass
import os


def _set_if_undefined(var: str):
    if not os.environ.get(var):
        os.environ[var] = getpass.getpass(f"Please provide your {var}")


_set_if_undefined("OPENAI_API_KEY")
_set_if_undefined("TAVILY_API_KEY")
```

Example 3 (python):
```python
from langchain_tavily import TavilySearch

web_search = TavilySearch(max_results=3)
web_search_results = web_search.invoke("who is the mayor of NYC?")

print(web_search_results["results"][0]["content"])
```

Example 4 (unknown):
```unknown
Find events, attractions, deals, and more at nyctourism.com Skip Main Navigation Menu The Official Website of the City of New York Text Size Powered by Translate SearchSearch Primary Navigation The official website of NYC Home NYC Resources NYC311 Office of the Mayor Events Connect Jobs Search Office of the Mayor | Mayor's Bio | City of New York Secondary Navigation MayorBiographyNewsOfficials Eric L. Adams 110th Mayor of New York City Mayor Eric Adams has served the people of New York City as an NYPD officer, State Senator, Brooklyn Borough President, and now as the 110th Mayor of the City of New York. Mayor Eric Adams has served the people of New York City as an NYPD officer, State Senator, Brooklyn Borough President, and now as the 110th Mayor of the City of New York. He gave voice to a diverse coalition of working families in all five boroughs and is leading the fight to bring back New York City's economy, reduce inequality, improve public safety, and build a stronger, healthier city that delivers for all New Yorkers. As the representative of one of the nation's largest counties, Eric fought tirelessly to grow the local economy, invest in schools, reduce inequality, improve public safety, and advocate for smart policies and better government that delivers for all New Yorkers.
```

---
