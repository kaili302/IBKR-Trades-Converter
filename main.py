import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Any
import os
import csv

@dataclass
class AccountInformation:
    accountId: str
    acctAlias: str
    currency: str
    dateOpened: str

@dataclass
class Trade:
    symbol: str
    transactionType: str
    exchange: str
    quantity: float
    tradePrice: float
    currency: str
    fxRateToBase: float
    assetCategory: str
    ibCommission: float
    ibCommissionCurrency: str
    tradeDate: str
    
    def side(self):
        return "SELL" if self.quantity < 0  else "BUY"
    
    def tradePriceInBaseCurrency(self):
        return abs(self.tradePrice * self.fxRateToBase)
    
    def ibCommissionInBaseCurrency(self):
        ibCommission = abs(self.ibCommission)
        if self.ibCommissionCurrency == self.currency:
            return ibCommission * self.fxRateToBase
        return ibCommission

@dataclass
class Lot:
    symbol: str
    transactionType: str
    exchange: str
    quantity: float
    tradePrice: float
    currency: str
    fxRateToBase: float
    assetCategory: str
    ibCommission: str
    ibCommissionCurrency: str
    tradeDate: str

@dataclass
class Trades:
    trade: List[Trade] = field(default_factory=list)
    lot: List[Lot] = field(default_factory=list)

@dataclass
class FlexStatement:
    accountId: str
    fromDate: str
    toDate: str
    period: str
    whenGenerated: str
    accountInformation: Optional[AccountInformation] = None
    trades: Optional[Trades] = None

@dataclass
class FlexStatements:
    count: int
    flexStatement: List[FlexStatement] = field(default_factory=list)

@dataclass
class FlexQueryResponse:
    queryName: str
    type: str
    flexStatements: Optional[FlexStatements] = None


def parse_xml(xml_string):
    root = ET.fromstring(xml_string)

    response = FlexQueryResponse(
        queryName=root.get("queryName"),
        type=root.get("type"),
    )

    flex_statements_elem = root.find("FlexStatements")
    if flex_statements_elem is not None:
        flex_statements = FlexStatements(
            count=int(flex_statements_elem.get("count"))
        )
        response.flexStatements = flex_statements

        for flex_statement_elem in flex_statements_elem.findall("FlexStatement"):
            flex_statement = FlexStatement(
                accountId=flex_statement_elem.get("accountId"),
                fromDate=flex_statement_elem.get("fromDate"),
                toDate=flex_statement_elem.get("toDate"),
                period=flex_statement_elem.get("period"),
                whenGenerated=flex_statement_elem.get("whenGenerated"),
            )
            flex_statements.flexStatement.append(flex_statement)

            account_info_elem = flex_statement_elem.find("AccountInformation")
            if account_info_elem is not None:
                flex_statement.accountInformation = AccountInformation(
                    accountId=account_info_elem.get("accountId"),
                    acctAlias=account_info_elem.get("acctAlias"),
                    currency=account_info_elem.get("currency"),
                    dateOpened=account_info_elem.get("dateOpened"),
                )
            trades_elem = flex_statement_elem.find("Trades")
            if trades_elem is not None:
                trades = Trades()
                flex_statement.trades = trades
                for trade_elem in trades_elem.findall("Trade"):
                    try:
                        ibCommission = float(trade_elem.get('ibCommission'))
                    except (ValueError, TypeError):
                        ibCommission = 0.0

                    trades.trade.append(Trade(
                        symbol=trade_elem.get("symbol"),
                        transactionType=trade_elem.get("transactionType"),
                        exchange=trade_elem.get("exchange"),
                        quantity=float(trade_elem.get("quantity")),
                        tradePrice=float(trade_elem.get("tradePrice")),
                        currency=trade_elem.get("currency"),
                        fxRateToBase=float(trade_elem.get("fxRateToBase")),
                        assetCategory=trade_elem.get("assetCategory"),
                        ibCommission=ibCommission,
                        ibCommissionCurrency=trade_elem.get("ibCommissionCurrency"),
                        tradeDate=trade_elem.get("tradeDate"),
                    ))
                for lot_elem in trades_elem.findall("Lot"):
                    trades.lot.append(Lot(
                        symbol=lot_elem.get("symbol"),
                        transactionType=lot_elem.get("transactionType"),
                        exchange=lot_elem.get("exchange"),
                        quantity=float(lot_elem.get("quantity")),
                        tradePrice=float(lot_elem.get("tradePrice")),
                        currency=lot_elem.get("currency"),
                        fxRateToBase=float(lot_elem.get("fxRateToBase")),
                        assetCategory=lot_elem.get("assetCategory"),
                        ibCommission=lot_elem.get("ibCommission"),
                        ibCommissionCurrency=lot_elem.get("ibCommissionCurrency"),
                        tradeDate=lot_elem.get("tradeDate"),
                    ))

    return response

@dataclass
class CgtCalculatorTrade:
    side: str
    date: str
    company: str
    shares: int
    price: float
    charges: float
    tax: int = 0

def convert(ibkrTrade : Trade) -> CgtCalculatorTrade:
    return CgtCalculatorTrade(
        side = ibkrTrade.side(),
        date = ibkrTrade.tradeDate,
        company= ibkrTrade.symbol,
        shares= int(abs(ibkrTrade.quantity)),
        price = ibkrTrade.tradePriceInBaseCurrency(),
        charges= ibkrTrade.ibCommissionInBaseCurrency()
    )
        
def process_xml_files(folder_path="data"):
    parsed_data_list = []
    for filename in os.listdir(folder_path):
        if filename.endswith(".xml"):
            filepath = os.path.join(folder_path, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    xml_string = f.read()
                parsed_data = parse_xml(xml_string)
                parsed_data_list.append(parsed_data)
            except ET.ParseError as e:
                print(f"Error parsing XML file {filename}: {e}")
            except Exception as e:
                print(f"An unexpected error occurred processing {filename}: {e}")
    return parsed_data_list


def get_trades_from_xmls() -> List[CgtCalculatorTrade]:
    trades = []
    parsed_data = process_xml_files("data")
    for data in parsed_data:
        for statement in data.flexStatements.flexStatement:
            for txn in statement.trades.trade:
                if txn.assetCategory == "CASH":
                    continue
                trades.append(convert(txn))
    return trades
        
def save_cgt_trades_to_csv(trades: List[CgtCalculatorTrade], filename: str):

    if not trades:
        print("No trades to write to CSV.")
        return

    fieldnames = list(asdict(trades[0]).keys())
    # "B/S","Date", "Company", "Shares", "Price", "Charges", "Tax"
    # B/S, Date, Company, Shares, Price, Charges, Tax

    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for trade in trades:
                writer.writerow(asdict(trade))
        print(f"Trades successfully saved to {filename}")
    except Exception as e:
        print(f"An error occurred while writing to the CSV file: {e}")

save_cgt_trades_to_csv(get_trades_from_xmls(), "trades.csv")