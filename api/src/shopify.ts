import { config } from './config.js';

interface CheckoutInput {
  size: string;
  phrase: string;
  discountCode?: string;
  customerId: string;
}

interface CheckoutResult {
  checkoutUrl: string;
  checkoutId: string;
}

// Size variant mapping - loaded from environment
function getVariantId(size: string): string | undefined {
  const sizeMap: Record<string, string> = {
    'xs': 'XS',
    'extra small': 'XS',
    's': 'S',
    'small': 'S',
    'm': 'M',
    'medium': 'M',
    'l': 'L',
    'large': 'L',
    'xl': 'XL',
    'extra large': 'XL',
    'xxl': '2XL',
    '2xl': '2XL',
    '2x': '2XL',
  };
  
  const normalized = sizeMap[size.toLowerCase()] || size.toUpperCase();
  const envKey = `SHOPIFY_VARIANT_${normalized}`;
  return process.env[envKey];
}

export async function createCheckout(input: CheckoutInput): Promise<CheckoutResult> {
  const { size, phrase, discountCode, customerId } = input;
  
  const variantId = getVariantId(size);
  if (!variantId) {
    console.error(`No variant ID found for size: ${size}`);
    throw new Error(`Invalid size: ${size}. Available: XS, S, M, L, XL, 2XL`);
  }
  
  // Build checkout URL with cart permalink
  const checkoutUrl = buildCheckoutUrl(variantId, phrase, discountCode, customerId);
  
  return {
    checkoutUrl,
    checkoutId: `checkout-${Date.now()}`
  };
}

function buildCheckoutUrl(variantId: string, phrase: string, discountCode?: string, customerId?: string): string {
  // Build a Shopify checkout URL with cart attributes
  // Format: /cart/VARIANT_ID:QUANTITY?attributes[key]=value
  
  const baseUrl = `https://${config.shopifyStoreUrl}/cart`;
  const cartUrl = `${baseUrl}/${variantId}:1`;
  
  // Add attributes - these appear in order details
  const params = new URLSearchParams();
  params.set('attributes[phrase]', phrase);
  params.set('attributes[customer_id]', customerId || 'anonymous');
  params.set('attributes[source]', 'monger-terminal');
  
  // Add discount code if present
  if (discountCode) {
    params.set('discount', discountCode);
  }
  
  return `${cartUrl}?${params.toString()}`;
}

// Alternative: Use Shopify GraphQL Storefront API for more control
export async function createCheckoutGraphQL(input: CheckoutInput): Promise<CheckoutResult> {
  const { size, phrase, discountCode, customerId } = input;
  
  // You would need a Storefront API access token (different from Admin API)
  const storefrontToken = process.env.SHOPIFY_STOREFRONT_TOKEN;
  
  if (!storefrontToken) {
    // Fall back to URL-based checkout
    return createCheckout(input);
  }
  
  const mutation = `
    mutation checkoutCreate($input: CheckoutCreateInput!) {
      checkoutCreate(input: $input) {
        checkout {
          id
          webUrl
        }
        checkoutUserErrors {
          code
          field
          message
        }
      }
    }
  `;
  
  const variantId = getVariantId(size);
  if (!variantId) {
    return createCheckout(input);
  }
  
  // Convert numeric ID to GID format for GraphQL
  const variantGid = `gid://shopify/ProductVariant/${variantId}`;
  
  const variables = {
    input: {
      lineItems: [
        {
          variantId: variantGid,
          quantity: 1,
          customAttributes: [
            { key: 'phrase', value: phrase },
            { key: 'customer_id', value: customerId },
            { key: 'source', value: 'monger-terminal' }
          ]
        }
      ],
      customAttributes: [
        { key: 'cheeseshirt_phrase', value: phrase }
      ]
    }
  };
  
  try {
    const response = await fetch(
      `https://${config.shopifyStoreUrl}/api/${config.shopifyApiVersion}/graphql.json`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Shopify-Storefront-Access-Token': storefrontToken
        },
        body: JSON.stringify({ query: mutation, variables })
      }
    );
    
    const data = await response.json();
    
    if (data.errors || data.data?.checkoutCreate?.checkoutUserErrors?.length > 0) {
      console.error('Checkout creation errors:', data.errors || data.data.checkoutCreate.checkoutUserErrors);
      // Fall back to URL-based checkout
      return createCheckout(input);
    }
    
    const checkout = data.data.checkoutCreate.checkout;
    
    // Apply discount code if present
    let checkoutUrl = checkout.webUrl;
    if (discountCode) {
      checkoutUrl += `?discount=${encodeURIComponent(discountCode)}`;
    }
    
    return {
      checkoutUrl,
      checkoutId: checkout.id
    };
    
  } catch (error) {
    console.error('GraphQL checkout error:', error);
    // Fall back to URL-based checkout
    return createCheckout(input);
  }
}

