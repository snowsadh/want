INVENTORY_PROMPT_VERSION = "outfit-inventory-v1"
SHOPPING_PROMPT_VERSION = "item-shopping-v1"


INVENTORY_PROMPT = """
Identify every distinct, separately shoppable item visibly worn by the main person in the supplied
reference image.

Include garments, footwear, legwear, bags, belts, scarves, hats, headbands, substantial hair
accessories and clearly visible statement jewelry. Ignore tiny or barely visible jewelry, tiny
decorative clips and non-wearable objects.

Return each visible item exactly once.

Rules:
- Do not invent hidden items or visually unsupported attributes.
- Treat a matching left/right pair of shoes, socks or leg warmers as one item.
- Keep separately shoppable overlapping layers as separate items.
- Do not create a separate item from only a small visible edge of an underlayer.
- Clothing tied around the waist remains that garment; do not relabel its sleeves or panels as a
  belt, sash or tie.
- Call an item a dress, romper or jumpsuit only when continuous construction across the waist is
  visible. Otherwise keep coordinated separates distinct.
- Use a tight [ymin, xmin, ymax, xmax] box normalized to 0..1000 for every item.
- Record only visible category, colors, silhouette, material appearance, pattern, print or graphic,
  construction and distinctive details.
- Use "unknown" when an attribute is not visually supported. Do not guess a brand, exact fabric
  composition or hidden construction.
- Mark an item partial or heavily occluded when its important shape is blocked or cut off.

Return only the structured inventory.
""".strip()


SHOPPING_PROMPT = """
Find up to three closest currently buyable new-retail matches for the supplied item.

Use the target crop to inspect the item. Use the full reference to resolve crop, layering or category
ambiguity. The structured item fields are visual notes; the supplied images remain the evidence.

The product category must match. Search for the identical product first. If it is unavailable, rank
alternatives by:

1. color and style/silhouette;
2. design and pattern layout;
3. print or exact graphic;
4. material, texture and smaller details.

Relax lower-priority details before higher-priority details. When a graphic or pattern covers most
of an item, its scale and placement are part of the style, not a minor keyword match.

Search using both image and text results. Choose the strongest attribute-rich query first. Judge
products from their images and product pages, not titles or shared keywords alone.

Every returned product must:
- be the same product category as the target;
- be a distinct, currently buyable new-retail product;
- have a direct product-page URL;
- have a product image URL showing the matching product and color variant;
- have a listed price and currency, or null when genuinely unavailable.

Exclude resale and second-hand products, category or search-result pages, editorial or inspiration
pages, products whose image does not show the item, and invented URLs, images, prices or
availability.

When equally useful images exist for the same product, prefer one showing a model wearing the item
only when the target item is clearly isolated and other clothing will not confuse virtual try-on.
Otherwise prefer the clean product image. This is a preference, not a requirement.

Use at most three web-search tool calls. Stop when three credible candidates have been found. Return
zero, one or two products rather than adding weak matches. Order products from closest visual match
to least close.

Return only the structured result.
""".strip()
