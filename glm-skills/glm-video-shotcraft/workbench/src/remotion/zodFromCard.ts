import { z } from "zod";
import { zColor } from "@remotion/zod-types";
import type { CardDef, PropField } from "../cards/types";

/** Converts workbench PropField schema into Zod schema for Studio Inspector form controls */
const fieldToZod = (f: PropField): z.ZodTypeAny => {
  switch (f.type) {
    case "text":
    case "textarea":
      return z.string().describe(f.label);
    case "number":
    case "slider": {
      let n = z.number();
      if (f.min !== undefined) n = n.min(f.min);
      if (f.max !== undefined) n = n.max(f.max);
      return n.describe(f.label);
    }
    case "color":
      return zColor().describe(f.label);
    case "select":
      return z
        .enum(f.options.map((o) => o.value) as [string, ...string[]])
        .describe(f.label);
    case "boolean":
      return z.boolean().describe(f.label);
  }
};

export const zodFromCard = (card: CardDef) =>
  z.object(Object.fromEntries(card.schema.map((f) => [f.key, fieldToZod(f)])));
