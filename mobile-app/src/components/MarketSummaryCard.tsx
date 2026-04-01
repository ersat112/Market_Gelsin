import { StyleSheet, Text, View } from "react-native";

import { MarketBasketSummary } from "../types";
import { theme } from "../theme";

type MarketSummaryCardProps = {
  summary: MarketBasketSummary;
  highlight?: boolean;
};

export function MarketSummaryCard({ summary, highlight = false }: MarketSummaryCardProps) {
  return (
    <View style={[styles.card, highlight ? styles.highlight : undefined]}>
      <View style={styles.header}>
        <Text style={styles.name}>{summary.marketName}</Text>
        <Text style={styles.total}>{summary.total.toFixed(2)} TL</Text>
      </View>
      <Text style={styles.meta}>{summary.matchedItems} urun bulundu</Text>
      {summary.missingItems.length > 0 ? (
        <Text style={styles.missing}>Eksikler: {summary.missingItems.join(", ")}</Text>
      ) : (
        <Text style={styles.complete}>Liste bu markette tamamen karsilaniyor.</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.colors.surface,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    gap: theme.spacing.xs,
    padding: theme.spacing.md
  },
  highlight: {
    backgroundColor: theme.colors.primarySoft,
    borderColor: theme.colors.primary
  },
  header: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between"
  },
  name: {
    color: theme.colors.text,
    fontSize: 16,
    fontWeight: "800"
  },
  total: {
    color: theme.colors.primary,
    fontSize: 17,
    fontWeight: "900"
  },
  meta: {
    color: theme.colors.textMuted,
    fontSize: 13
  },
  missing: {
    color: theme.colors.warning,
    fontSize: 13,
    lineHeight: 18
  },
  complete: {
    color: theme.colors.success,
    fontSize: 13,
    lineHeight: 18
  }
});
