// db_bootstrap.js
(() => {
  // --- Config depuis l'environnement/--eval, avec fallback ---
  if (typeof DB_NAME === 'undefined') { var DB_NAME = 'turbodex'; }
  if (typeof SEED === 'undefined')   { var SEED = false; }
  SEED = (SEED === true || SEED === 'true');

  const conn = db.getMongo();
  const database = conn.getDB(DB_NAME);
  print(`[bootstrap] DB=${DB_NAME} SEED=${SEED}`);

  function ensureCollection(name, validation) {
  const exists = database.getCollectionNames().includes(name);
  if (!exists) {
    const optsWithValidator = {};
    if (validation && validation.$jsonSchema) {
      optsWithValidator.validator = validation;
    }
    try {
      database.createCollection(name, optsWithValidator);
      print(`- created ${name} (with validator)`);
    } catch (e) {
      const msg = (e && e.toString()) || "";
      // Cosmos DB (API Mongo) ne supporte pas validator -> on retente SANS validator
      if (msg.match(/validator not supported/i) || msg.match(/not implemented/i)) {
        try {
          database.createCollection(name); // sans validator
          print(`- created ${name} (no validator - Cosmos)`);
        } catch (e2) {
          print(`- create ${name} failed (even without validator): ${e2}`);
        }
      } else {
        print(`- create ${name} failed (ignored): ${e}`);
      }
    }
  } else {
    print(`- ${name} exists`);
  }
  return database.getCollection(name);
}


  function ensureIndex(coll, keys, opts) {
    opts = Object.assign({}, opts || {});
    try {
      const res = coll.createIndex(keys, opts);
      print(`  idx ${coll.getName()}: ${res}`);
    } catch (e) {
      print(`  idx ${coll.getName()} ERROR (ignored): ${e}`);
    }
  }

  // ---------- users ----------
  const users = ensureCollection('users', {
    $jsonSchema: {
      bsonType: "object",
      required: ["username","username_ci","password_hash","created_at"],
      properties: {
        username:      { bsonType: "string" },
        username_ci:   { bsonType: "string" }, // username en lowercase
        email:         { bsonType: ["string","null"] },
        password_hash: { bsonType: "string" },
        roles:         { bsonType: "array" },
        profile:       { bsonType: "object" },
        stats:         { bsonType: "object" },
        created_at:    { bsonType: "date" },
        updated_at:    { bsonType: ["date","null"] },
        last_login_at: { bsonType: ["date","null"] }
      }
    }
  });
  ensureIndex(users, { username_ci: 1 }, { name: "username_ci_1", unique: true });
  ensureIndex(users, { email: 1 },       { name: "email_1", unique: false, sparse: true });
  ensureIndex(users, { "stats.points": -1 }, { name: "points_desc" });

  // ---------- tokens (refresh sessions) ----------
  const tokens = ensureCollection('tokens', {
    $jsonSchema: {
      bsonType: "object",
      required: ["user_id","token_hash","created_at","expires_at"],
      properties: {
        user_id:    { bsonType: "objectId" },
        token_hash: { bsonType: "string" },
        revoked:    { bsonType: ["bool","null"] },
        created_at: { bsonType: "date" },
        expires_at: { bsonType: "date" }
      }
    }
  });
  ensureIndex(tokens, { token_hash: 1 }, { name: "token_hash_1", unique: true });
  ensureIndex(tokens, { user_id: 1 },    { name: "token_user_1" });
  try {
    tokens.createIndex({ expires_at: 1 }, { expireAfterSeconds: 0, name: "ttl_by_expires" });
    print("  idx tokens ttl_by_expires");
  } catch(e) { print("  idx tokens ttl_by_expires ERROR (ignored): " + e); }

  // ---------- posts ----------
  const posts = ensureCollection('posts', {
    $jsonSchema: {
      bsonType: "object",
      required: ["user_id","blob_name","status","created_at"],
      properties: {
        user_id:            { bsonType: "objectId" },
        blob_name:          { bsonType: "string" },         // dans container raw
        processed_blob_url: { bsonType: ["string","null"] },// dans container processed
        status:             { enum: ["pending","processed","rejected"] },
        taken_at:           { bsonType: ["date","null"] },
        created_at:         { bsonType: "date" },
        rejected_reason:    { bsonType: ["string","null"] },
        location:           { bsonType: "object" }, // {city,country,lat,lon}
        vehicle: { // meta véhicule détecté/assigné
          bsonType: "object",
          properties: {
            vehicle_id: { bsonType: ["objectId","null"] },
            brand:      { bsonType: ["string","null"] },
            model:      { bsonType: ["string","null"] },
            body_type:  { bsonType: ["string","null"] },
            engine_type:{ bsonType: ["string","null"] },
            plate:      { bsonType: ["string","null"] },
            rarity:     { bsonType: ["string","null"] } // e.g. 'Common','Rare','Epic','Legendary'
          }
        },
        like_count:         { bsonType: ["int","long","null"] },
        comment_count:      { bsonType: ["int","long","null"] }
      }
    }
  });
  ensureIndex(posts, { user_id: 1, created_at: -1 }, { name: "user_created" });
  ensureIndex(posts, { created_at: -1 },             { name: "created_desc" });
  ensureIndex(posts, { status: 1, created_at: -1 },  { name: "status_created" });
  ensureIndex(posts, { "vehicle.brand": 1, "vehicle.model": 1 }, { name: "vehicle_brand_model" });
  ensureIndex(posts, { "vehicle.plate": 1 }, { name: "vehicle_plate_1", sparse: true });

  // ---------- likes ----------
  const likes = ensureCollection('likes', {
    $jsonSchema: {
      bsonType: "object",
      required: ["user_id","post_id","created_at"],
      properties: {
        user_id:    { bsonType: "objectId" },
        post_id:    { bsonType: "objectId" },
        created_at: { bsonType: "date" }
      }
    }
  });
  ensureIndex(likes, { post_id: 1 }, { name: "likes_by_post" });
  ensureIndex(likes, { user_id: 1 }, { name: "likes_by_user" });
  ensureIndex(likes, { user_id: 1, post_id: 1 }, { name: "user_post_unique", unique: true });

  // ---------- achievements (catalogue) ----------
  const achievements = ensureCollection('achievements', {
    $jsonSchema: {
      bsonType: "object",
      required: ["key","title","points"],
      properties: {
        key:         { bsonType: "string" },
        title:       { bsonType: "string" },
        description: { bsonType: ["string","null"] },
        icon:        { bsonType: ["string","null"] },
        points:      { bsonType: ["int","long"] }
      }
    }
  });
  ensureIndex(achievements, { key: 1 }, { name: "key_1", unique: true });

  // ---------- user_achievements (liens user <-> achievement) ----------
  const userAch = ensureCollection('user_achievements', {
    $jsonSchema: {
      bsonType: "object",
      required: ["user_id","achievement_key","unlocked_at"],
      properties: {
        user_id:        { bsonType: "objectId" },
        achievement_key:{ bsonType: "string" },
        unlocked_at:    { bsonType: "date" }
      }
    }
  });
  ensureIndex(userAch, { user_id: 1 },                          { name: "ua_by_user" });
  ensureIndex(userAch, { achievement_key: 1 },                  { name: "ua_by_key" });
  ensureIndex(userAch, { user_id: 1, achievement_key: 1 },      { name: "ua_unique", unique: true });

  // ---------- cars (référentiel de modèles) ----------
  const cars = ensureCollection('cars', {
    $jsonSchema: {
      bsonType: "object",
      required: ["brand","model"],
      properties: {
        brand:      { bsonType: "string" },
        model:      { bsonType: "string" },
        body_type:  { bsonType: ["string","null"] },
        engine_type:{ bsonType: ["string","null"] },
        year_from:  { bsonType: ["int","null"] },
        year_to:    { bsonType: ["int","null"] },
        tags:       { bsonType: "array" }
      }
    }
  });
  ensureIndex(cars, { brand: 1, model: 1, body_type: 1 }, { name: "brand_model_body" });
  ensureIndex(cars, { model: 1 },                         { name: "model_1" });

  // ---------- follows (relations utilisateur -> utilisateur) ----------
  const follows = ensureCollection('follows', {
    $jsonSchema: {
      bsonType: "object",
      required: ["follower_id","followee_id","created_at"],
      properties: {
        follower_id:{ bsonType: "objectId" },
        followee_id:{ bsonType: "objectId" },
        created_at: { bsonType: "date" }
      }
    }
  });
  ensureIndex(follows, { follower_id: 1 },                   { name: "by_follower" });
  ensureIndex(follows, { followee_id: 1 },                   { name: "by_followee" });
  ensureIndex(follows, { follower_id: 1, followee_id: 1 },   { name: "follow_unique", unique: true });

  // ---------- turbodex (classements/périodes) ----------
  const turbodex = ensureCollection('turbodex', {
    $jsonSchema: {
      bsonType: "object",
      required: ["user_id","period","points","updated_at"],
      properties: {
        user_id:    { bsonType: "objectId" },
        period:     { enum: ["daily","weekly","monthly","all"] },
        points:     { bsonType: ["int","long"] },
        rank:       { bsonType: ["int","long","null"] },
        updated_at: { bsonType: "date" }
      }
    }
  });
  ensureIndex(turbodex, { period: 1, points: -1 }, { name: "period_points_desc" });
  ensureIndex(turbodex, { user_id: 1, period: 1 }, { name: "user_period_unique", unique: true });

  // ---------- audit_logs (optionnel pour debug) ----------
  const audit = ensureCollection('audit_logs', {
    $jsonSchema: {
      bsonType: "object",
      required: ["ts","actor","action"],
      properties: {
        ts:     { bsonType: "date" },
        actor:  { bsonType: ["objectId","null"] },
        action: { bsonType: "string" },
        meta:   { bsonType: "object" }
      }
    }
  });
  ensureIndex(audit, { ts: -1 }, { name: "ts_desc" });

  // ---------- Seed minimal (achievements) ----------
  if (SEED) {
    const defaults = [
      {key:"first_post", title:"Premier post", points:10, description:"Publier une première photo"},
      {key:"first_like", title:"Premier like", points:2, description:"Liker une photo"},
      {key:"ten_posts",  title:"10 posts",     points:50, description:"Publier 10 photos"},
      {key:"rare_spot",  title:"Détection rare", points:100, description:"Repérer un véhicule rare"}
    ];
    defaults.forEach(doc => {
      try {
        achievements.updateOne({key: doc.key}, {$setOnInsert: doc}, {upsert: true});
      } catch (e) { print("seed ach error (ignored):", e); }
    });
    print("Seeded achievements count:",
          achievements.countDocuments({key: {$in: defaults.map(d=>d.key)}}));
  }

  // Résumé des index
  function printIndexes(coll) {
    const idx = coll.getIndexes().map(i => i.name);
    print(`  -> indexes[${coll.getName()}]: ${idx.join(", ")}`);
  }
  [users,tokens,posts,likes,achievements,userAch,cars,follows,turbodex,audit].forEach(printIndexes);

  print("[bootstrap] done.");
})();

