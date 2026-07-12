import type { BrowserHistoryTarget, RouteDeckClient } from "@routedeck/core";

import { medusaRouteDeckClient } from "../routedeck/client";
import {
  createMedusaRouteDeck,
  type MedusaRouteDeck,
} from "./createRouteDeck";

export async function loadMedusaRouteDeck(
  browser: BrowserHistoryTarget,
  client: RouteDeckClient = medusaRouteDeckClient,
): Promise<MedusaRouteDeck> {
  const contract = await client.getFrontendContract();
  return createMedusaRouteDeck({ contract, browser, client });
}
