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

// Size variant mapping - these IDs would come from your Shopify product
const SIZE_VARIANTS: Record<string, string> = {
  's': 'gid://shopify/ProductVariant/small-variant-id',
  'm': 'gid://shopify/ProductVariant/medium-variant-id',
  'l': 'gid://shopify/ProductVariant/large-variant-id',
  'xl': 'gid://shopify/ProductVariant/xl-variant-id',
  'xxl': 'gid://shopify/ProductVariant/xxl-variant-id',
};

export async function createCheckout(input: CheckoutInput): Promise<CheckoutResult> {
  const { size, phrase, discountCode, customerId } = input;
  
  const variantId = SIZE_VARIANTS[size.toLowerCase()];
  if (!variantId) {
    throw new Error(`Invalid size: ${size}`);
  }
  
  // Create checkout using Shopify Storefront API
  // For now, we'll use a direct link approach that works with standard Shopify
  const checkoutUrl = buildCheckoutUrl(size, phrase, discountCode, customerId);
  
  return {
    checkoutUrl,
    checkoutId: `checkout-${Date.now()}`
  };
}

function buildCheckoutUrl(size: string, phrase: string, discountCode?: string, customerId?: string): string {
  // Build a Shopify checkout URL with cart attributes
  // This uses Shopify's cart permalink format
  
  const baseUrl = `https://${config.shopifyStoreUrl}/cart`;
  
  // You'll need to set up your actual variant IDs in Shopify
  // Format: /cart/VARIANT_ID:QUANTITY
  // For now, using a placeholder that you'll configure
  const variantId = process.env[`SHOPIFY_VARIANT_${size.toUpperCase()}`] || '00000000000';
  
  const cartUrl = `${baseUrl}/${variantId}:1`;
  
  // Add attributes
  const params = new URLSearchParams();
  
  // Custom attributes are passed as attributes[key]=value
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
  
  const variantId = SIZE_VARIANTS[size.toLowerCase()];
  
  const variables = {
    input: {
      lineItems: [
        {
          variantId,
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

