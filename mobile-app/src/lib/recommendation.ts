import { markets, priceEntries } from "../data/seed";
import { BasketAnalysis, CityId, MarketBasketSummary, PriceEntry, ProductRecommendation } from "../types";

const normalize = (value: string) =>
  value
    .toLocaleLowerCase("tr-TR")
    .replace(/[^a-z0-9\s]/gi, " ")
    .replace(/\s+/g, " ")
    .trim();

const tokenize = (value: string) => normalize(value).split(" ").filter(Boolean);

const isMatch = (requestedItem: string, productName: string) => {
  const requestedTokens = tokenize(requestedItem);
  const productText = normalize(productName);

  if (requestedTokens.length === 0) {
    return false;
  }

  return requestedTokens.every((token) => productText.includes(token));
};

const sortCheapest = (items: PriceEntry[]) => [...items].sort((left, right) => left.price - right.price);

export const parseShoppingList = (rawInput: string) =>
  rawInput
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);

export const getMarketsForCity = (cityId: CityId) => markets.filter((market) => market.cityId === cityId);

export const getSearchResults = (cityId: CityId, searchTerm: string) => {
  const term = searchTerm.trim();

  if (!term) {
    return [];
  }

  return sortCheapest(priceEntries.filter((entry) => entry.cityId === cityId && isMatch(term, entry.productName)));
};

const getProductRecommendations = (cityId: CityId, requestedItems: string[]): ProductRecommendation[] =>
  requestedItems.map((requestedItem) => {
    const options = sortCheapest(
      priceEntries.filter((entry) => entry.cityId === cityId && isMatch(requestedItem, entry.productName))
    );

    return {
      requestedItem,
      found: options.length > 0,
      bestOption: options[0],
      options
    };
  });

const buildMarketTotals = (recommendations: ProductRecommendation[]): MarketBasketSummary[] =>
  markets
    .map((market) => {
      const matchedOptions = recommendations
        .map((recommendation) => recommendation.options.find((option) => option.marketId === market.id))
        .filter((option): option is PriceEntry => Boolean(option));

      if (matchedOptions.length === 0) {
        return undefined;
      }

      const missingItems = recommendations
        .filter((recommendation) => !matchedOptions.some((option) => isMatch(recommendation.requestedItem, option.productName)))
        .map((recommendation) => recommendation.requestedItem);

      return {
        marketId: market.id,
        marketName: market.name,
        matchedItems: matchedOptions.length,
        missingItems,
        total: Number(matchedOptions.reduce((sum, option) => sum + option.price, 0).toFixed(2))
      };
    })
    .filter((summary): summary is MarketBasketSummary => Boolean(summary))
    .sort((left, right) => {
      if (right.matchedItems !== left.matchedItems) {
        return right.matchedItems - left.matchedItems;
      }

      return left.total - right.total;
    });

export const analyzeBasket = (cityId: CityId, requestedItems: string[]): BasketAnalysis => {
  const productRecommendations = getProductRecommendations(cityId, requestedItems);
  const marketTotals = buildMarketTotals(productRecommendations).filter((summary) =>
    markets.some((market) => market.id === summary.marketId && market.cityId === cityId)
  );
  const splitBasketTotal = Number(
    productRecommendations.reduce((sum, recommendation) => sum + (recommendation.bestOption?.price ?? 0), 0).toFixed(2)
  );
  const completeMarkets = marketTotals
    .filter((summary) => summary.matchedItems === requestedItems.length)
    .sort((left, right) => left.total - right.total);

  return {
    requestedItems,
    productRecommendations,
    splitBasketTotal,
    bestSingleMarket: completeMarkets[0] ?? marketTotals[0],
    marketTotals
  };
};
