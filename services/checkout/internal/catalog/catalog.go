// Package catalog reads product data from the marketplace service.
//
// Prices come from here, never from the client: a browser that can name its
// own price is a coupon generator.
package catalog

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
)

type Product struct {
	ID         string `json:"id"`
	Title      string `json:"title"`
	PriceMinor int64  `json:"price_minor"`
	Currency   string `json:"currency"`
	InStock    bool   `json:"in_stock"`
	Artisan    struct {
		DisplayName string `json:"display_name"`
	} `json:"artisan"`
}

type Client struct {
	baseURL string
	http    *http.Client
}

func New(baseURL string, timeout time.Duration) *Client {
	return &Client{
		baseURL: strings.TrimRight(baseURL, "/"),
		// Every outbound call gets a timeout: without one a slow dependency
		// holds this service's goroutines until it runs out of them.
		http: &http.Client{
			Timeout: timeout,
			// Records the call as a span and sends the trace headers with it,
			// so marketplace's work appears inside the order that caused it.
			Transport: otelhttp.NewTransport(http.DefaultTransport),
		},
	}
}

// ProductsByID fetches several products in one request, keyed by id.
func (c *Client) ProductsByID(ctx context.Context, ids []string) (map[string]Product, error) {
	if len(ids) == 0 {
		return map[string]Product{}, nil
	}

	url := fmt.Sprintf("%s/products?ids=%s&limit=%d", c.baseURL, strings.Join(ids, ","), len(ids))
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "application/json")

	resp, err := c.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("catalog unreachable: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("catalog returned %d", resp.StatusCode)
	}

	var page struct {
		Results []Product `json:"results"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&page); err != nil {
		return nil, fmt.Errorf("catalog response: %w", err)
	}

	products := make(map[string]Product, len(page.Results))
	for _, product := range page.Results {
		products[product.ID] = product
	}
	return products, nil
}
