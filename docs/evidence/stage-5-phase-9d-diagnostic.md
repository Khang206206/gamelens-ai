# Stage 5 / 9D functional diagnostic

Project-authored six-game fixture. Functional arithmetic only; Stage 6 evaluation remains deferred.

## Provenance

```json
{
  "fixture": "stage-5-9d-six-games-v1",
  "catalog_fingerprint": "8e1c434d08e2176f92c8647bbab526c4f1eaadfb19c76436cf28563f88e76507",
  "interaction_fingerprint": "b968e7a3692a5afa23ffcc6f6fe3228af3dbc9ba55b4adfcf18cdc335f00805f",
  "build_id": "stage5-9d-diagnostic-v1",
  "content_model": ["gamelens-content-tfidf", "1.0.0"],
  "collaborative_model": ["gamelens-item-item-cosine", "1.0.0"],
  "content_item_axis": [
    "a-source",
    "b-both",
    "c-content",
    "d-collaborative",
    "e-cold",
    "z-tie"
  ],
  "collaborative_item_axis": [
    "a-source",
    "b-both",
    "c-content",
    "d-collaborative",
    "z-tie"
  ],
  "vocabulary_sha256": "c067aff71c3f2a78725a81e9321876a3838c805bf0fef98a651e8a0f322262f4",
  "scoring_policy": {
    "name": "gamelens-collaborative-scoring",
    "version": "1.0.0"
  },
  "feedback_policy": {
    "name": "gamelens-feedback-adjustment",
    "version": "1.0.0"
  },
  "hybrid_policy": {
    "name": "gamelens-hybrid-ranking",
    "version": "1.0.0"
  },
  "popularity_config": {
    "minimum_vote_prior": 50,
    "rating_weight_units": 700000,
    "signal_weight_units": 300000,
    "missing_rating_policy": "catalog-weighted-mean",
    "constant_range_value_units": 500000
  },
  "content_config": {
    "score_scale": 1000000,
    "selected_game_weight_units": 650000,
    "taxonomy_weight_units": 350000,
    "content_weight_units": 800000,
    "platform_weight_units": 100000,
    "popularity_weight_units": 100000,
    "rounding": "half-up",
    "tie_break": [
      "final_score_desc",
      "content_score_desc",
      "popularity_score_desc",
      "slug_asc"
    ]
  },
  "semantic_arrays": {
    "content.data": {
      "dtype": "float64",
      "shape": [32],
      "sha256": "b8ad5f733f5791d92af7f38c0ba2dece3fe1f7890cce196a365ffe3ca66a2a3f"
    },
    "content.indices": {
      "dtype": "int32",
      "shape": [32],
      "sha256": "a16e8ed6fb80171cab6732842b36277d54c2f32186f681892222c746d080dd8f"
    },
    "content.indptr": {
      "dtype": "int32",
      "shape": [7],
      "sha256": "c5e6bd230e572a0224ab70512209fb0af459db76649625f6b18ae2715ecd1999"
    },
    "content.idf": {
      "dtype": "float64",
      "shape": [14],
      "sha256": "8ca5e71f8967194bfad612d1c71647bda06f5fc4fe1c3b12ce37712da0d4337c"
    },
    "content.popularity": {
      "dtype": "float64",
      "shape": [6],
      "sha256": "c63f57ea9b467bbd38a7060a87ecd94836153a3765a27826c61a41ec70ee8cf2"
    },
    "collaborative.item_support": {
      "dtype": "int64",
      "shape": [5],
      "sha256": "c8fd6a47f4a4b310bfbd4906cc27f0c489bcd39feee02b1a9a73d8e30a905054"
    },
    "collaborative.neighbor_indices": {
      "dtype": "int32",
      "shape": [16],
      "sha256": "578040cf34c94aab45b6a83a82bd02e7ea842006a417c8b3a9c3d935a4c6c167"
    },
    "collaborative.neighbor_indptr": {
      "dtype": "int32",
      "shape": [6],
      "sha256": "27f9dcadbc5acb8c9fa225c93302b4122907d8ec1fd17e46518a5e7c60581dcb"
    },
    "collaborative.similarity_units": {
      "dtype": "int32",
      "shape": [16],
      "sha256": "c732a6dfcdeac29ebe333de1d137886e36ecef5b8851c59e096c7adbed9e607b"
    },
    "collaborative.pair_support": {
      "dtype": "int64",
      "shape": [16],
      "sha256": "c0e674dd2475cd6ea4e15ac1b3592e63d056725f79467cbcf3b724a8811729a5"
    }
  }
}
```

## Variant contracts

- **popularity**: Full catalog minus saved selections; ignores reactions/played/wishlist. Uses popularity_baseline, then diagnostic-only (-units, slug), then top-K. No content/support requirement or fallback.
- **content**: Native ContentRanker: positive quantized content, minus saved selections; ignores feedback. (-base, -content, -popularity, slug), then top-K. Zero content stays ineligible; empty reason is no_content_support.
- **feedback**: Native FeedbackRanker: effective content candidates minus saved/positive/disliked games before top-K. (-final, -pre-played, -base, -affinity, -content, -popularity, slug). Weights base/affinity 90/10 when active, otherwise 100/0; one played factor. Empty reason distinguishes no content from all excluded.
- **collaborative**: Native CollaborativeScorer: retained neighbors of supported query sources minus all query sources and dislikes. (-score, slug); diagnostic takes top-K after native exclusions/order. No content or played adjustment; absent support returns an explicit reason and no rows. Mean uses only contributing retained edges.
- **hybrid**: Native HybridRanker: content/retained-neighbor union minus saved/positive/disliked games before top-K. (-final, -pre-played, -base contribution, -collaborative contribution, -affinity contribution, -content, -popularity, slug). Request-wide base/affinity/collaborative 80/10/10 or 90/0/10; missing edge retains its weight with zero contribution. One played factor; no support wraps exact Stage 4.

All units use scale 1000000 and half-up rounding. `—` means absent/inapplicable; missing hybrid edges retain a zero contribution, not a measured score. Base cells list content/platform/popularity as raw:weight:contribution. Outer weights/contributions are base/affinity/collaborative (single component for pure variants). Played cells are factor:delta. Edge cells are source:kind:similarity:pair-support. Every table contains all returned rows; top-K and exclusions appear in its context.

## Hand derivation and observed differences

All six ratings are 8 with 100 votes, so the normalized rating signal is 0.5. Popularity is 0.7*0.5 + 0.3*(catalog signal/100): 350000, 500000 or 650000 units. The four tactical documents are identical; orbital and sandbox documents are orthogonal to them. A tactical unigram query has cosine (1+ln(3))/sqrt(2*(1+ln(3))^2+(1+ln(2))^2+3), or 547825 units. The cold-item scenario uses the existing 65/35 saved/taxonomy mixture, yielding content cosines 880471 (tactical) and 259724 (sandbox).

Ten synthetic profiles produce item supports a/d=8, b/z=10, c=2; e is absent. Pairs a-d=8 and a-b/a-z=8 give cosines 1000000 and 894427. Pair c-z=2 gives 447214; a-c is absent. In the top-one scenario, d averages the two retained source edges to 947214; c uses only its retained z edge, without dilution.

For b in supported_played, base is 800000+100000+50000=950000. Feedback applies (855000+100000)*0.5=477500; hybrid applies (760000+100000+89443)*0.5, rounded once to 474722. The source liked and saved as a is counted once. Candidate c has no a edge: its hybrid contributions stay 748000+100000+0=848000 under 80/10/10. Candidate d has zero content yet joins the hybrid union with base 165000 and final 132000+0+100000=232000. Content/feedback omit d because their content eligibility is unchanged. Wishlist neutrality is checked by full-result equality in the focused suite. These differences describe arithmetic and eligibility only.

## supported_played

```json
{
  "context": {
    "selected_game_slugs": ["a-source"],
    "preferred_genres": [],
    "preferred_tags": [],
    "preferred_platforms": ["pc"],
    "top_k": 20
  },
  "feedback": [
    {
      "game_slug": "a-source",
      "reaction": "liked",
      "played": false,
      "wishlisted": false,
      "rating": null
    },
    {
      "game_slug": "b-both",
      "reaction": null,
      "played": true,
      "wishlisted": false,
      "rating": null
    }
  ],
  "sources": [{ "game_slug": "a-source", "kind": "liked" }],
  "supported_sources": ["a-source"],
  "unsupported_sources": [],
  "exclusions": ["a-source"]
}
```

| Variant / reason               | Rank / game / origin                | Base components                                                     | Base / affinity / collaborative | Support / edges              | Weights              | Contributions       | Pre-played | Played         | Final   |
| ------------------------------ | ----------------------------------- | ------------------------------------------------------------------- | ------------------------------- | ---------------------------- | -------------------- | ------------------- | ---------- | -------------- | ------- |
| popularity: recommendations    | 1 / d-collaborative / catalog       | —                                                                   | popularity=650000               | — / —                        | 1000000              | 650000              | —          | —:—            | 650000  |
| popularity: recommendations    | 2 / b-both / catalog                | —                                                                   | popularity=500000               | — / —                        | 1000000              | 500000              | —          | —:—            | 500000  |
| popularity: recommendations    | 3 / z-tie / catalog                 | —                                                                   | popularity=500000               | — / —                        | 1000000              | 500000              | —          | —:—            | 500000  |
| popularity: recommendations    | 4 / c-content / catalog             | —                                                                   | popularity=350000               | — / —                        | 1000000              | 350000              | —          | —:—            | 350000  |
| popularity: recommendations    | 5 / e-cold / catalog                | —                                                                   | popularity=350000               | — / —                        | 1000000              | 350000              | —          | —:—            | 350000  |
| content: recommendations       | 1 / b-both / content                | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/—/—                      | — / —                        | 1000000/0/0          | 950000/0/0          | 950000     | 1000000:0      | 950000  |
| content: recommendations       | 2 / z-tie / content                 | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/—/—                      | — / —                        | 1000000/0/0          | 950000/0/0          | 950000     | 1000000:0      | 950000  |
| content: recommendations       | 3 / c-content / content             | 1000000:800000:800000 / 1000000:100000:100000 / 350000:100000:35000 | 935000/—/—                      | — / —                        | 1000000/0/0          | 935000/0/0          | 935000     | 1000000:0      | 935000  |
| feedback: recommendations      | 1 / z-tie / content                 | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/1000000/—                | — / —                        | 900000/100000/0      | 855000/100000/0     | 955000     | 1000000:0      | 955000  |
| feedback: recommendations      | 2 / c-content / content             | 1000000:800000:800000 / 1000000:100000:100000 / 350000:100000:35000 | 935000/1000000/—                | — / —                        | 900000/100000/0      | 841500/100000/0     | 941500     | 1000000:0      | 941500  |
| feedback: recommendations      | 3 / b-both / content                | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/1000000/—                | — / —                        | 900000/100000/0      | 855000/100000/0     | 955000     | 500000:-477500 | 477500  |
| collaborative: recommendations | 1 / d-collaborative / collaborative | —                                                                   | —/—/1000000                     | 8 / a-source:liked:1000000:8 | 1000000              | 1000000             | —          | —:—            | 1000000 |
| collaborative: recommendations | 2 / b-both / collaborative          | —                                                                   | —/—/894427                      | 10 / a-source:liked:894427:8 | 1000000              | 894427              | —          | —:—            | 894427  |
| collaborative: recommendations | 3 / z-tie / collaborative           | —                                                                   | —/—/894427                      | 10 / a-source:liked:894427:8 | 1000000              | 894427              | —          | —:—            | 894427  |
| hybrid: recommendations        | 1 / z-tie / both                    | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/1000000/894427           | 10 / a-source:liked:894427:8 | 800000/100000/100000 | 760000/100000/89443 | 949443     | 1000000:0      | 949443  |
| hybrid: recommendations        | 2 / c-content / content             | 1000000:800000:800000 / 1000000:100000:100000 / 350000:100000:35000 | 935000/1000000/—                | — / —                        | 800000/100000/100000 | 748000/100000/0     | 848000     | 1000000:0      | 848000  |
| hybrid: recommendations        | 3 / b-both / both                   | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/1000000/894427           | 10 / a-source:liked:894427:8 | 800000/100000/100000 | 760000/100000/89443 | 949443     | 500000:-474721 | 474722  |
| hybrid: recommendations        | 4 / d-collaborative / collaborative | 0:800000:0 / 1000000:100000:100000 / 650000:100000:65000            | 165000/0/1000000                | 8 / a-source:liked:1000000:8 | 800000/100000/100000 | 132000/0/100000     | 232000     | 1000000:0      | 232000  |

## saved_only_tied

```json
{
  "context": {
    "selected_game_slugs": ["a-source"],
    "preferred_genres": [],
    "preferred_tags": [],
    "preferred_platforms": ["pc"],
    "top_k": 20
  },
  "feedback": [],
  "sources": [{ "game_slug": "a-source", "kind": "saved_game" }],
  "supported_sources": ["a-source"],
  "unsupported_sources": [],
  "exclusions": ["a-source"]
}
```

| Variant / reason               | Rank / game / origin                | Base components                                                     | Base / affinity / collaborative | Support / edges                   | Weights         | Contributions   | Pre-played | Played    | Final   |
| ------------------------------ | ----------------------------------- | ------------------------------------------------------------------- | ------------------------------- | --------------------------------- | --------------- | --------------- | ---------- | --------- | ------- |
| popularity: recommendations    | 1 / d-collaborative / catalog       | —                                                                   | popularity=650000               | — / —                             | 1000000         | 650000          | —          | —:—       | 650000  |
| popularity: recommendations    | 2 / b-both / catalog                | —                                                                   | popularity=500000               | — / —                             | 1000000         | 500000          | —          | —:—       | 500000  |
| popularity: recommendations    | 3 / z-tie / catalog                 | —                                                                   | popularity=500000               | — / —                             | 1000000         | 500000          | —          | —:—       | 500000  |
| popularity: recommendations    | 4 / c-content / catalog             | —                                                                   | popularity=350000               | — / —                             | 1000000         | 350000          | —          | —:—       | 350000  |
| popularity: recommendations    | 5 / e-cold / catalog                | —                                                                   | popularity=350000               | — / —                             | 1000000         | 350000          | —          | —:—       | 350000  |
| content: recommendations       | 1 / b-both / content                | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/—/—                      | — / —                             | 1000000/0/0     | 950000/0/0      | 950000     | 1000000:0 | 950000  |
| content: recommendations       | 2 / z-tie / content                 | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/—/—                      | — / —                             | 1000000/0/0     | 950000/0/0      | 950000     | 1000000:0 | 950000  |
| content: recommendations       | 3 / c-content / content             | 1000000:800000:800000 / 1000000:100000:100000 / 350000:100000:35000 | 935000/—/—                      | — / —                             | 1000000/0/0     | 935000/0/0      | 935000     | 1000000:0 | 935000  |
| feedback: recommendations      | 1 / b-both / content                | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/—/—                      | — / —                             | 1000000/0/0     | 950000/0/0      | 950000     | 1000000:0 | 950000  |
| feedback: recommendations      | 2 / z-tie / content                 | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/—/—                      | — / —                             | 1000000/0/0     | 950000/0/0      | 950000     | 1000000:0 | 950000  |
| feedback: recommendations      | 3 / c-content / content             | 1000000:800000:800000 / 1000000:100000:100000 / 350000:100000:35000 | 935000/—/—                      | — / —                             | 1000000/0/0     | 935000/0/0      | 935000     | 1000000:0 | 935000  |
| collaborative: recommendations | 1 / d-collaborative / collaborative | —                                                                   | —/—/1000000                     | 8 / a-source:saved_game:1000000:8 | 1000000         | 1000000         | —          | —:—       | 1000000 |
| collaborative: recommendations | 2 / b-both / collaborative          | —                                                                   | —/—/894427                      | 10 / a-source:saved_game:894427:8 | 1000000         | 894427          | —          | —:—       | 894427  |
| collaborative: recommendations | 3 / z-tie / collaborative           | —                                                                   | —/—/894427                      | 10 / a-source:saved_game:894427:8 | 1000000         | 894427          | —          | —:—       | 894427  |
| hybrid: recommendations        | 1 / b-both / both                   | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/—/894427                 | 10 / a-source:saved_game:894427:8 | 900000/0/100000 | 855000/0/89443  | 944443     | 1000000:0 | 944443  |
| hybrid: recommendations        | 2 / z-tie / both                    | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/—/894427                 | 10 / a-source:saved_game:894427:8 | 900000/0/100000 | 855000/0/89443  | 944443     | 1000000:0 | 944443  |
| hybrid: recommendations        | 3 / c-content / content             | 1000000:800000:800000 / 1000000:100000:100000 / 350000:100000:35000 | 935000/—/—                      | — / —                             | 900000/0/100000 | 841500/0/0      | 841500     | 1000000:0 | 841500  |
| hybrid: recommendations        | 4 / d-collaborative / collaborative | 0:800000:0 / 1000000:100000:100000 / 650000:100000:65000            | 165000/—/1000000                | 8 / a-source:saved_game:1000000:8 | 900000/0/100000 | 148500/0/100000 | 248500     | 1000000:0 | 248500  |

## cold_user

```json
{
  "context": {
    "selected_game_slugs": [],
    "preferred_genres": ["strategy"],
    "preferred_tags": [],
    "preferred_platforms": ["pc"],
    "top_k": 20
  },
  "feedback": [],
  "sources": [],
  "supported_sources": [],
  "unsupported_sources": [],
  "exclusions": []
}
```

| Variant / reason                                            | Rank / game / origin          | Base components                                                    | Base / affinity / collaborative | Support / edges | Weights     | Contributions | Pre-played | Played    | Final  |
| ----------------------------------------------------------- | ----------------------------- | ------------------------------------------------------------------ | ------------------------------- | --------------- | ----------- | ------------- | ---------- | --------- | ------ |
| popularity: recommendations                                 | 1 / a-source / catalog        | —                                                                  | popularity=650000               | — / —           | 1000000     | 650000        | —          | —:—       | 650000 |
| popularity: recommendations                                 | 2 / d-collaborative / catalog | —                                                                  | popularity=650000               | — / —           | 1000000     | 650000        | —          | —:—       | 650000 |
| popularity: recommendations                                 | 3 / b-both / catalog          | —                                                                  | popularity=500000               | — / —           | 1000000     | 500000        | —          | —:—       | 500000 |
| popularity: recommendations                                 | 4 / z-tie / catalog           | —                                                                  | popularity=500000               | — / —           | 1000000     | 500000        | —          | —:—       | 500000 |
| popularity: recommendations                                 | 5 / c-content / catalog       | —                                                                  | popularity=350000               | — / —           | 1000000     | 350000        | —          | —:—       | 350000 |
| popularity: recommendations                                 | 6 / e-cold / catalog          | —                                                                  | popularity=350000               | — / —           | 1000000     | 350000        | —          | —:—       | 350000 |
| content: recommendations                                    | 1 / a-source / content        | 547825:800000:438260 / 1000000:100000:100000 / 650000:100000:65000 | 603260/—/—                      | — / —           | 1000000/0/0 | 603260/0/0    | 603260     | 1000000:0 | 603260 |
| content: recommendations                                    | 2 / b-both / content          | 547825:800000:438260 / 1000000:100000:100000 / 500000:100000:50000 | 588260/—/—                      | — / —           | 1000000/0/0 | 588260/0/0    | 588260     | 1000000:0 | 588260 |
| content: recommendations                                    | 3 / z-tie / content           | 547825:800000:438260 / 1000000:100000:100000 / 500000:100000:50000 | 588260/—/—                      | — / —           | 1000000/0/0 | 588260/0/0    | 588260     | 1000000:0 | 588260 |
| content: recommendations                                    | 4 / c-content / content       | 547825:800000:438260 / 1000000:100000:100000 / 350000:100000:35000 | 573260/—/—                      | — / —           | 1000000/0/0 | 573260/0/0    | 573260     | 1000000:0 | 573260 |
| feedback: recommendations                                   | 1 / a-source / content        | 547825:800000:438260 / 1000000:100000:100000 / 650000:100000:65000 | 603260/—/—                      | — / —           | 1000000/0/0 | 603260/0/0    | 603260     | 1000000:0 | 603260 |
| feedback: recommendations                                   | 2 / b-both / content          | 547825:800000:438260 / 1000000:100000:100000 / 500000:100000:50000 | 588260/—/—                      | — / —           | 1000000/0/0 | 588260/0/0    | 588260     | 1000000:0 | 588260 |
| feedback: recommendations                                   | 3 / z-tie / content           | 547825:800000:438260 / 1000000:100000:100000 / 500000:100000:50000 | 588260/—/—                      | — / —           | 1000000/0/0 | 588260/0/0    | 588260     | 1000000:0 | 588260 |
| feedback: recommendations                                   | 4 / c-content / content       | 547825:800000:438260 / 1000000:100000:100000 / 350000:100000:35000 | 573260/—/—                      | — / —           | 1000000/0/0 | 573260/0/0    | 573260     | 1000000:0 | 573260 |
| collaborative: no_query_sources                             | empty                         | —                                                                  | —                               | —               | —           | —             | —          | —         | —      |
| hybrid: recommendations; stage_4_fallback: no_query_sources | 1 / a-source / content        | 547825:800000:438260 / 1000000:100000:100000 / 650000:100000:65000 | 603260/—/—                      | — / —           | 1000000/0/0 | 603260/0/0    | 603260     | 1000000:0 | 603260 |
| hybrid: recommendations; stage_4_fallback: no_query_sources | 2 / b-both / content          | 547825:800000:438260 / 1000000:100000:100000 / 500000:100000:50000 | 588260/—/—                      | — / —           | 1000000/0/0 | 588260/0/0    | 588260     | 1000000:0 | 588260 |
| hybrid: recommendations; stage_4_fallback: no_query_sources | 3 / z-tie / content           | 547825:800000:438260 / 1000000:100000:100000 / 500000:100000:50000 | 588260/—/—                      | — / —           | 1000000/0/0 | 588260/0/0    | 588260     | 1000000:0 | 588260 |
| hybrid: recommendations; stage_4_fallback: no_query_sources | 4 / c-content / content       | 547825:800000:438260 / 1000000:100000:100000 / 350000:100000:35000 | 573260/—/—                      | — / —           | 1000000/0/0 | 573260/0/0    | 573260     | 1000000:0 | 573260 |

## cold_source_empty

```json
{
  "context": {
    "selected_game_slugs": ["e-cold"],
    "preferred_genres": [],
    "preferred_tags": [],
    "preferred_platforms": [],
    "top_k": 20
  },
  "feedback": [],
  "sources": [{ "game_slug": "e-cold", "kind": "saved_game" }],
  "supported_sources": [],
  "unsupported_sources": ["e-cold"],
  "exclusions": ["e-cold"]
}
```

| Variant / reason                                                   | Rank / game / origin          | Base components | Base / affinity / collaborative | Support / edges | Weights | Contributions | Pre-played | Played | Final  |
| ------------------------------------------------------------------ | ----------------------------- | --------------- | ------------------------------- | --------------- | ------- | ------------- | ---------- | ------ | ------ |
| popularity: recommendations                                        | 1 / a-source / catalog        | —               | popularity=650000               | — / —           | 1000000 | 650000        | —          | —:—    | 650000 |
| popularity: recommendations                                        | 2 / d-collaborative / catalog | —               | popularity=650000               | — / —           | 1000000 | 650000        | —          | —:—    | 650000 |
| popularity: recommendations                                        | 3 / b-both / catalog          | —               | popularity=500000               | — / —           | 1000000 | 500000        | —          | —:—    | 500000 |
| popularity: recommendations                                        | 4 / z-tie / catalog           | —               | popularity=500000               | — / —           | 1000000 | 500000        | —          | —:—    | 500000 |
| popularity: recommendations                                        | 5 / c-content / catalog       | —               | popularity=350000               | — / —           | 1000000 | 350000        | —          | —:—    | 350000 |
| content: no_content_support                                        | empty                         | —               | —                               | —               | —       | —             | —          | —      | —      |
| feedback: no_content_support                                       | empty                         | —               | —                               | —               | —       | —             | —          | —      | —      |
| collaborative: no_supported_sources                                | empty                         | —               | —                               | —               | —       | —             | —          | —      | —      |
| hybrid: no_content_support; stage_4_fallback: no_supported_sources | empty                         | —               | —                               | —               | —       | —             | —          | —      | —      |

## mixed_sources

```json
{
  "context": {
    "selected_game_slugs": ["a-source"],
    "preferred_genres": [],
    "preferred_tags": [],
    "preferred_platforms": ["pc"],
    "top_k": 20
  },
  "feedback": [
    {
      "game_slug": "e-cold",
      "reaction": "liked",
      "played": false,
      "wishlisted": false,
      "rating": null
    }
  ],
  "sources": [
    { "game_slug": "e-cold", "kind": "liked" },
    { "game_slug": "a-source", "kind": "saved_game" }
  ],
  "supported_sources": ["a-source"],
  "unsupported_sources": ["e-cold"],
  "exclusions": ["a-source", "e-cold"]
}
```

| Variant / reason               | Rank / game / origin                | Base components                                                     | Base / affinity / collaborative | Support / edges                   | Weights              | Contributions   | Pre-played | Played    | Final   |
| ------------------------------ | ----------------------------------- | ------------------------------------------------------------------- | ------------------------------- | --------------------------------- | -------------------- | --------------- | ---------- | --------- | ------- |
| popularity: recommendations    | 1 / d-collaborative / catalog       | —                                                                   | popularity=650000               | — / —                             | 1000000              | 650000          | —          | —:—       | 650000  |
| popularity: recommendations    | 2 / b-both / catalog                | —                                                                   | popularity=500000               | — / —                             | 1000000              | 500000          | —          | —:—       | 500000  |
| popularity: recommendations    | 3 / z-tie / catalog                 | —                                                                   | popularity=500000               | — / —                             | 1000000              | 500000          | —          | —:—       | 500000  |
| popularity: recommendations    | 4 / c-content / catalog             | —                                                                   | popularity=350000               | — / —                             | 1000000              | 350000          | —          | —:—       | 350000  |
| popularity: recommendations    | 5 / e-cold / catalog                | —                                                                   | popularity=350000               | — / —                             | 1000000              | 350000          | —          | —:—       | 350000  |
| content: recommendations       | 1 / b-both / content                | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/—/—                      | — / —                             | 1000000/0/0          | 950000/0/0      | 950000     | 1000000:0 | 950000  |
| content: recommendations       | 2 / z-tie / content                 | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/—/—                      | — / —                             | 1000000/0/0          | 950000/0/0      | 950000     | 1000000:0 | 950000  |
| content: recommendations       | 3 / c-content / content             | 1000000:800000:800000 / 1000000:100000:100000 / 350000:100000:35000 | 935000/—/—                      | — / —                             | 1000000/0/0          | 935000/0/0      | 935000     | 1000000:0 | 935000  |
| feedback: recommendations      | 1 / b-both / content                | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/0/—                      | — / —                             | 900000/100000/0      | 855000/0/0      | 855000     | 1000000:0 | 855000  |
| feedback: recommendations      | 2 / z-tie / content                 | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/0/—                      | — / —                             | 900000/100000/0      | 855000/0/0      | 855000     | 1000000:0 | 855000  |
| feedback: recommendations      | 3 / c-content / content             | 1000000:800000:800000 / 1000000:100000:100000 / 350000:100000:35000 | 935000/0/—                      | — / —                             | 900000/100000/0      | 841500/0/0      | 841500     | 1000000:0 | 841500  |
| collaborative: recommendations | 1 / d-collaborative / collaborative | —                                                                   | —/—/1000000                     | 8 / a-source:saved_game:1000000:8 | 1000000              | 1000000         | —          | —:—       | 1000000 |
| collaborative: recommendations | 2 / b-both / collaborative          | —                                                                   | —/—/894427                      | 10 / a-source:saved_game:894427:8 | 1000000              | 894427          | —          | —:—       | 894427  |
| collaborative: recommendations | 3 / z-tie / collaborative           | —                                                                   | —/—/894427                      | 10 / a-source:saved_game:894427:8 | 1000000              | 894427          | —          | —:—       | 894427  |
| hybrid: recommendations        | 1 / b-both / both                   | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/0/894427                 | 10 / a-source:saved_game:894427:8 | 800000/100000/100000 | 760000/0/89443  | 849443     | 1000000:0 | 849443  |
| hybrid: recommendations        | 2 / z-tie / both                    | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/0/894427                 | 10 / a-source:saved_game:894427:8 | 800000/100000/100000 | 760000/0/89443  | 849443     | 1000000:0 | 849443  |
| hybrid: recommendations        | 3 / c-content / content             | 1000000:800000:800000 / 1000000:100000:100000 / 350000:100000:35000 | 935000/0/—                      | — / —                             | 800000/100000/100000 | 748000/0/0      | 748000     | 1000000:0 | 748000  |
| hybrid: recommendations        | 4 / d-collaborative / collaborative | 0:800000:0 / 1000000:100000:100000 / 650000:100000:65000            | 165000/0/1000000                | 8 / a-source:saved_game:1000000:8 | 800000/100000/100000 | 132000/0/100000 | 232000     | 1000000:0 | 232000  |

## cold_content_item

```json
{
  "context": {
    "selected_game_slugs": ["a-source"],
    "preferred_genres": ["sandbox"],
    "preferred_tags": [],
    "preferred_platforms": ["pc"],
    "top_k": 20
  },
  "feedback": [],
  "sources": [{ "game_slug": "a-source", "kind": "saved_game" }],
  "supported_sources": ["a-source"],
  "unsupported_sources": [],
  "exclusions": ["a-source"]
}
```

| Variant / reason               | Rank / game / origin                | Base components                                                    | Base / affinity / collaborative | Support / edges                   | Weights         | Contributions   | Pre-played | Played    | Final   |
| ------------------------------ | ----------------------------------- | ------------------------------------------------------------------ | ------------------------------- | --------------------------------- | --------------- | --------------- | ---------- | --------- | ------- |
| popularity: recommendations    | 1 / d-collaborative / catalog       | —                                                                  | popularity=650000               | — / —                             | 1000000         | 650000          | —          | —:—       | 650000  |
| popularity: recommendations    | 2 / b-both / catalog                | —                                                                  | popularity=500000               | — / —                             | 1000000         | 500000          | —          | —:—       | 500000  |
| popularity: recommendations    | 3 / z-tie / catalog                 | —                                                                  | popularity=500000               | — / —                             | 1000000         | 500000          | —          | —:—       | 500000  |
| popularity: recommendations    | 4 / c-content / catalog             | —                                                                  | popularity=350000               | — / —                             | 1000000         | 350000          | —          | —:—       | 350000  |
| popularity: recommendations    | 5 / e-cold / catalog                | —                                                                  | popularity=350000               | — / —                             | 1000000         | 350000          | —          | —:—       | 350000  |
| content: recommendations       | 1 / b-both / content                | 880471:800000:704377 / 1000000:100000:100000 / 500000:100000:50000 | 854377/—/—                      | — / —                             | 1000000/0/0     | 854377/0/0      | 854377     | 1000000:0 | 854377  |
| content: recommendations       | 2 / z-tie / content                 | 880471:800000:704377 / 1000000:100000:100000 / 500000:100000:50000 | 854377/—/—                      | — / —                             | 1000000/0/0     | 854377/0/0      | 854377     | 1000000:0 | 854377  |
| content: recommendations       | 3 / c-content / content             | 880471:800000:704377 / 1000000:100000:100000 / 350000:100000:35000 | 839377/—/—                      | — / —                             | 1000000/0/0     | 839377/0/0      | 839377     | 1000000:0 | 839377  |
| content: recommendations       | 4 / e-cold / content                | 259724:800000:207779 / 1000000:100000:100000 / 350000:100000:35000 | 342779/—/—                      | — / —                             | 1000000/0/0     | 342779/0/0      | 342779     | 1000000:0 | 342779  |
| feedback: recommendations      | 1 / b-both / content                | 880471:800000:704377 / 1000000:100000:100000 / 500000:100000:50000 | 854377/—/—                      | — / —                             | 1000000/0/0     | 854377/0/0      | 854377     | 1000000:0 | 854377  |
| feedback: recommendations      | 2 / z-tie / content                 | 880471:800000:704377 / 1000000:100000:100000 / 500000:100000:50000 | 854377/—/—                      | — / —                             | 1000000/0/0     | 854377/0/0      | 854377     | 1000000:0 | 854377  |
| feedback: recommendations      | 3 / c-content / content             | 880471:800000:704377 / 1000000:100000:100000 / 350000:100000:35000 | 839377/—/—                      | — / —                             | 1000000/0/0     | 839377/0/0      | 839377     | 1000000:0 | 839377  |
| feedback: recommendations      | 4 / e-cold / content                | 259724:800000:207779 / 1000000:100000:100000 / 350000:100000:35000 | 342779/—/—                      | — / —                             | 1000000/0/0     | 342779/0/0      | 342779     | 1000000:0 | 342779  |
| collaborative: recommendations | 1 / d-collaborative / collaborative | —                                                                  | —/—/1000000                     | 8 / a-source:saved_game:1000000:8 | 1000000         | 1000000         | —          | —:—       | 1000000 |
| collaborative: recommendations | 2 / b-both / collaborative          | —                                                                  | —/—/894427                      | 10 / a-source:saved_game:894427:8 | 1000000         | 894427          | —          | —:—       | 894427  |
| collaborative: recommendations | 3 / z-tie / collaborative           | —                                                                  | —/—/894427                      | 10 / a-source:saved_game:894427:8 | 1000000         | 894427          | —          | —:—       | 894427  |
| hybrid: recommendations        | 1 / b-both / both                   | 880471:800000:704377 / 1000000:100000:100000 / 500000:100000:50000 | 854377/—/894427                 | 10 / a-source:saved_game:894427:8 | 900000/0/100000 | 768939/0/89443  | 858382     | 1000000:0 | 858382  |
| hybrid: recommendations        | 2 / z-tie / both                    | 880471:800000:704377 / 1000000:100000:100000 / 500000:100000:50000 | 854377/—/894427                 | 10 / a-source:saved_game:894427:8 | 900000/0/100000 | 768939/0/89443  | 858382     | 1000000:0 | 858382  |
| hybrid: recommendations        | 3 / c-content / content             | 880471:800000:704377 / 1000000:100000:100000 / 350000:100000:35000 | 839377/—/—                      | — / —                             | 900000/0/100000 | 755439/0/0      | 755439     | 1000000:0 | 755439  |
| hybrid: recommendations        | 4 / e-cold / content                | 259724:800000:207779 / 1000000:100000:100000 / 350000:100000:35000 | 342779/—/—                      | — / —                             | 900000/0/100000 | 308501/0/0      | 308501     | 1000000:0 | 308501  |
| hybrid: recommendations        | 5 / d-collaborative / collaborative | 0:800000:0 / 1000000:100000:100000 / 650000:100000:65000           | 165000/—/1000000                | 8 / a-source:saved_game:1000000:8 | 900000/0/100000 | 148500/0/100000 | 248500     | 1000000:0 | 248500  |

## all_eligible_excluded

```json
{
  "context": {
    "selected_game_slugs": ["a-source"],
    "preferred_genres": [],
    "preferred_tags": [],
    "preferred_platforms": ["pc"],
    "top_k": 20
  },
  "feedback": [
    {
      "game_slug": "b-both",
      "reaction": "disliked",
      "played": false,
      "wishlisted": false,
      "rating": null
    },
    {
      "game_slug": "c-content",
      "reaction": "liked",
      "played": false,
      "wishlisted": false,
      "rating": null
    },
    {
      "game_slug": "d-collaborative",
      "reaction": "disliked",
      "played": false,
      "wishlisted": false,
      "rating": null
    },
    {
      "game_slug": "z-tie",
      "reaction": "disliked",
      "played": false,
      "wishlisted": false,
      "rating": null
    }
  ],
  "sources": [
    { "game_slug": "c-content", "kind": "liked" },
    { "game_slug": "a-source", "kind": "saved_game" }
  ],
  "supported_sources": ["c-content", "a-source"],
  "unsupported_sources": [],
  "exclusions": ["a-source", "b-both", "c-content", "d-collaborative", "z-tie"]
}
```

| Variant / reason                                                         | Rank / game / origin          | Base components                                                     | Base / affinity / collaborative | Support / edges | Weights     | Contributions | Pre-played | Played    | Final  |
| ------------------------------------------------------------------------ | ----------------------------- | ------------------------------------------------------------------- | ------------------------------- | --------------- | ----------- | ------------- | ---------- | --------- | ------ |
| popularity: recommendations                                              | 1 / d-collaborative / catalog | —                                                                   | popularity=650000               | — / —           | 1000000     | 650000        | —          | —:—       | 650000 |
| popularity: recommendations                                              | 2 / b-both / catalog          | —                                                                   | popularity=500000               | — / —           | 1000000     | 500000        | —          | —:—       | 500000 |
| popularity: recommendations                                              | 3 / z-tie / catalog           | —                                                                   | popularity=500000               | — / —           | 1000000     | 500000        | —          | —:—       | 500000 |
| popularity: recommendations                                              | 4 / c-content / catalog       | —                                                                   | popularity=350000               | — / —           | 1000000     | 350000        | —          | —:—       | 350000 |
| popularity: recommendations                                              | 5 / e-cold / catalog          | —                                                                   | popularity=350000               | — / —           | 1000000     | 350000        | —          | —:—       | 350000 |
| content: recommendations                                                 | 1 / b-both / content          | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/—/—                      | — / —           | 1000000/0/0 | 950000/0/0    | 950000     | 1000000:0 | 950000 |
| content: recommendations                                                 | 2 / z-tie / content           | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/—/—                      | — / —           | 1000000/0/0 | 950000/0/0    | 950000     | 1000000:0 | 950000 |
| content: recommendations                                                 | 3 / c-content / content       | 1000000:800000:800000 / 1000000:100000:100000 / 350000:100000:35000 | 935000/—/—                      | — / —           | 1000000/0/0 | 935000/0/0    | 935000     | 1000000:0 | 935000 |
| feedback: no_eligible_candidates                                         | empty                         | —                                                                   | —                               | —               | —           | —             | —          | —         | —      |
| collaborative: no_eligible_candidates                                    | empty                         | —                                                                   | —                               | —               | —           | —             | —          | —         | —      |
| hybrid: no_eligible_candidates; stage_4_fallback: no_eligible_candidates | empty                         | —                                                                   | —                               | —               | —           | —             | —          | —         | —      |

## exclusions_top_one

```json
{
  "context": {
    "selected_game_slugs": ["a-source"],
    "preferred_genres": [],
    "preferred_tags": [],
    "preferred_platforms": ["pc"],
    "top_k": 1
  },
  "feedback": [
    {
      "game_slug": "b-both",
      "reaction": "disliked",
      "played": false,
      "wishlisted": false,
      "rating": null
    },
    {
      "game_slug": "c-content",
      "reaction": null,
      "played": true,
      "wishlisted": false,
      "rating": null
    },
    {
      "game_slug": "z-tie",
      "reaction": "liked",
      "played": false,
      "wishlisted": false,
      "rating": null
    }
  ],
  "sources": [
    { "game_slug": "z-tie", "kind": "liked" },
    { "game_slug": "a-source", "kind": "saved_game" }
  ],
  "supported_sources": ["z-tie", "a-source"],
  "unsupported_sources": [],
  "exclusions": ["a-source", "b-both", "z-tie"]
}
```

| Variant / reason               | Rank / game / origin                | Base components                                                     | Base / affinity / collaborative | Support / edges                                         | Weights              | Contributions       | Pre-played | Played         | Final  |
| ------------------------------ | ----------------------------------- | ------------------------------------------------------------------- | ------------------------------- | ------------------------------------------------------- | -------------------- | ------------------- | ---------- | -------------- | ------ |
| popularity: recommendations    | 1 / d-collaborative / catalog       | —                                                                   | popularity=650000               | — / —                                                   | 1000000              | 650000              | —          | —:—            | 650000 |
| content: recommendations       | 1 / b-both / content                | 1000000:800000:800000 / 1000000:100000:100000 / 500000:100000:50000 | 950000/—/—                      | — / —                                                   | 1000000/0/0          | 950000/0/0          | 950000     | 1000000:0      | 950000 |
| feedback: recommendations      | 1 / c-content / content             | 1000000:800000:800000 / 1000000:100000:100000 / 350000:100000:35000 | 935000/1000000/—                | — / —                                                   | 900000/100000/0      | 841500/100000/0     | 941500     | 500000:-470750 | 470750 |
| collaborative: recommendations | 1 / d-collaborative / collaborative | —                                                                   | —/—/947214                      | 8 / a-source:saved_game:1000000:8, z-tie:liked:894427:8 | 1000000              | 947214              | —          | —:—            | 947214 |
| hybrid: recommendations        | 1 / c-content / both                | 1000000:800000:800000 / 1000000:100000:100000 / 350000:100000:35000 | 935000/1000000/447214           | 2 / z-tie:liked:447214:2                                | 800000/100000/100000 | 748000/100000/44721 | 892721     | 500000:-446360 | 446361 |
