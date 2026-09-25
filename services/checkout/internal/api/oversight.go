package api

import (
	"errors"
	"net/http"
	"strings"

	"github.com/Tarunno/Poshra/services/checkout/internal/store"
)

// How many of a buyer's orders a support lookup returns. Enough to answer
// "has this happened before", not enough to be a browsing history.
const supportHistory = 20

// adminRole is taken from the header the gateway sets off the signed token.
//
// Unlike marketplace, this service has no user table to ask, so the header is
// what there is. It is trustworthy for the same reason the user id is: the
// gateway strips any client-supplied copy on every request, authenticated or
// not, and sets it from a token it verified.
const adminRole = "admin"

func isAdmin(r *http.Request) bool {
	return strings.EqualFold(strings.TrimSpace(r.Header.Get("X-User-Role")), adminRole)
}

// lookUpOrder answers "what happened with this order", for somebody holding an
// order number a customer gave them.
//
// A lookup, not a list. There is no way here to page through customers or to
// ask what a named person has been buying: support arrives with an order
// number, so an order number is the only way in. Every call is logged with the
// administrator who made it and whose order they opened, because an audit
// trail is what separates looking something up from browsing.
func (s *Server) lookUpOrder(w http.ResponseWriter, r *http.Request, orderID string) {
	if !isAdmin(r) {
		// 403 rather than 404: somebody signed in and refused should be told
		// they were refused, or they report it as broken.
		writeError(w, http.StatusForbidden, "This needs an administrator.")
		return
	}

	order, err := s.store.OrderByID(r.Context(), orderID)
	if errors.Is(err, store.ErrNotFound) {
		writeError(w, http.StatusNotFound, "No order with that number.")
		return
	}
	if err != nil {
		s.fail(w, "look up order", err)
		return
	}

	history, err := s.store.Orders(r.Context(), order.UserID, supportHistory)
	if err != nil {
		s.fail(w, "look up the buyer's other orders", err)
		return
	}

	s.log.Info("support looked up an order",
		"actor_id", userIDFrom(r),
		"order_id", order.ID,
		// Whose it was, so the record says what was seen and not only that
		// something was.
		"buyer_id", order.UserID,
		"request_id", requestIDFrom(r.Context()),
	)

	writeJSON(w, http.StatusOK, map[string]any{"order": order, "history": history})
}
