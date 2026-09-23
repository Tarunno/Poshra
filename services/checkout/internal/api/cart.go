package api

import (
	"encoding/json"
	"net/http"

	"github.com/google/uuid"

	"github.com/Tarunno/Poshra/services/checkout/internal/store"
)

type cartItemRequest struct {
	SKUID    string `json:"sku_id"`
	Quantity int32  `json:"quantity"`
}

// getCart returns the cart priced from the catalog, so the totals a buyer sees
// are the ones the order will use.
func (s *Server) getCart(w http.ResponseWriter, r *http.Request) {
	userID := userIDFrom(r)
	if userID == "" {
		writeError(w, http.StatusUnauthorized, "authentication required")
		return
	}

	items, err := s.store.Cart(r.Context(), userID)
	if err != nil {
		s.fail(w, "load cart", err)
		return
	}
	if len(items) == 0 {
		writeJSON(w, http.StatusOK, map[string]any{
			"items": []any{}, "total_minor": 0, "currency": "BDT",
		})
		return
	}

	ids := make([]string, 0, len(items))
	for _, item := range items {
		ids = append(ids, item.SKUID)
	}

	ctx, cancel := contextWithTimeout(r, s.cfg.CatalogTimeout)
	defer cancel()
	products, err := s.catalog.ProductsByID(ctx, ids)
	if err != nil {
		s.fail(w, "price cart", err)
		return
	}

	type line struct {
		SKUID       string `json:"sku_id"`
		Quantity    int32  `json:"quantity"`
		Title       string `json:"title"`
		UnitMinor   int64  `json:"unit_minor"`
		LineMinor   int64  `json:"line_minor"`
		Currency    string `json:"currency"`
		ArtisanName string `json:"artisan_name"`
		Available   bool   `json:"available"`
	}

	lines := make([]line, 0, len(items))
	var total int64
	currency := "BDT"
	for _, item := range items {
		product, ok := products[item.SKUID]
		if !ok {
			// Withdrawn since it was added: shown, but not counted, so the
			// buyer can see what changed.
			lines = append(lines, line{SKUID: item.SKUID, Quantity: item.Quantity, Available: false})
			continue
		}
		currency = product.Currency
		lineTotal := product.PriceMinor * int64(item.Quantity)
		total += lineTotal
		lines = append(lines, line{
			SKUID: item.SKUID, Quantity: item.Quantity, Title: product.Title,
			UnitMinor: product.PriceMinor, LineMinor: lineTotal, Currency: product.Currency,
			ArtisanName: product.Artisan.DisplayName, Available: product.InStock,
		})
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"items": lines, "total_minor": total, "currency": currency,
	})
}

func (s *Server) addCartItem(w http.ResponseWriter, r *http.Request) {
	userID := userIDFrom(r)
	if userID == "" {
		writeError(w, http.StatusUnauthorized, "authentication required")
		return
	}

	var body cartItemRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid json")
		return
	}
	if _, err := uuid.Parse(body.SKUID); err != nil {
		writeError(w, http.StatusBadRequest, "sku_id must be a uuid")
		return
	}
	if body.Quantity <= 0 {
		body.Quantity = 1
	}
	// A cap keeps one request from reserving an artisan's whole stock by
	// accident, and keeps the number sane for a handmade marketplace.
	if body.Quantity > 20 {
		writeError(w, http.StatusBadRequest, "quantity is limited to 20 per piece")
		return
	}

	if err := s.store.AddToCart(r.Context(), userID, body.SKUID, body.Quantity); err != nil {
		s.fail(w, "add to cart", err)
		return
	}
	s.getCart(w, r)
}

func (s *Server) setCartItem(w http.ResponseWriter, r *http.Request) {
	userID := userIDFrom(r)
	if userID == "" {
		writeError(w, http.StatusUnauthorized, "authentication required")
		return
	}
	sku := r.PathValue("sku")
	if _, err := uuid.Parse(sku); err != nil {
		writeError(w, http.StatusBadRequest, "sku must be a uuid")
		return
	}

	var body cartItemRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeError(w, http.StatusBadRequest, "invalid json")
		return
	}
	if body.Quantity > 20 {
		writeError(w, http.StatusBadRequest, "quantity is limited to 20 per piece")
		return
	}

	if err := s.store.SetCartQuantity(r.Context(), userID, sku, body.Quantity); err != nil {
		s.fail(w, "update cart", err)
		return
	}
	s.getCart(w, r)
}

func (s *Server) deleteCartItem(w http.ResponseWriter, r *http.Request) {
	userID := userIDFrom(r)
	if userID == "" {
		writeError(w, http.StatusUnauthorized, "authentication required")
		return
	}
	if err := s.store.RemoveFromCart(r.Context(), userID, r.PathValue("sku")); err != nil {
		s.fail(w, "remove from cart", err)
		return
	}
	s.getCart(w, r)
}

func (s *Server) clearCart(w http.ResponseWriter, r *http.Request) {
	userID := userIDFrom(r)
	if userID == "" {
		writeError(w, http.StatusUnauthorized, "authentication required")
		return
	}
	if err := s.store.ClearCart(r.Context(), userID); err != nil {
		s.fail(w, "clear cart", err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"items": []store.CartItem{}, "total_minor": 0})
}
