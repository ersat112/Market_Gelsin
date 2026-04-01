import { StyleSheet, Text, View } from "react-native";

import { ProductRecommendation } from "../types";
import { theme } from "../theme";

type RecommendationRowProps = {
  recommendation: ProductRecommendation;
};

export function RecommendationRow({ recommendation }: RecommendationRowProps) {
  if (!recommendation.found || !recommendation.bestOption) {
    return (
      <View style={styles.row}>
        <View style={styles.copy}>
          <Text style={styles.label}>{recommendation.requestedItem}</Text>
          <Text style={styles.meta}>Bu urun secili sehirde bulunamadi.</Text>
        </View>
        <Text style={styles.missing}>Eksik</Text>
      </View>
    );
  }

  return (
    <View style={styles.row}>
      <View style={styles.copy}>
        <Text style={styles.label}>{recommendation.requestedItem}</Text>
        <Text style={styles.meta}>
          {recommendation.bestOption.productName} - {recommendation.bestOption.freshnessLabel}
        </Text>
      </View>
      <View style={styles.priceBlock}>
        <Text style={styles.marketName}>{recommendation.bestOption.marketId.replace(/-/g, " ")}</Text>
        <Text style={styles.price}>{recommendation.bestOption.price.toFixed(2)} TL</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    alignItems: "center",
    borderBottomColor: theme.colors.border,
    borderBottomWidth: 1,
    flexDirection: "row",
    gap: theme.spacing.md,
    justifyContent: "space-between",
    paddingBottom: theme.spacing.md
  },
  copy: {
    flex: 1,
    gap: 4
  },
  label: {
    color: theme.colors.text,
    fontSize: 15,
    fontWeight: "700"
  },
  meta: {
    color: theme.colors.textMuted,
    fontSize: 13,
    lineHeight: 18
  },
  priceBlock: {
    alignItems: "flex-end",
    gap: 2
  },
  marketName: {
    color: theme.colors.textMuted,
    fontSize: 11,
    textTransform: "capitalize"
  },
  price: {
    color: theme.colors.primary,
    fontSize: 16,
    fontWeight: "800"
  },
  missing: {
    color: theme.colors.warning,
    fontSize: 13,
    fontWeight: "700"
  }
});
