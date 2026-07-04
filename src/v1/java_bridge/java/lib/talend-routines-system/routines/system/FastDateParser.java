// ============================================================================
//
// Copyright (C) 2006-2021 Talend Inc. - www.talend.com
//
// This source code is available under agreement available at
// %InstallDIR%\features\org.talend.rcp.branding.%PRODUCTNAME%\%PRODUCTNAME%license.txt
//
// You should have received a copy of the agreement
// along with this program; if not, write to Talend SA
// 9 rue Pages 92150 Suresnes, France
//
// ============================================================================
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
// ============================================================================
//
// Vendored from Talend Open Studio 8.0.1 (Talaxie community fork).
// See lib/LICENSE-talend-routines-system.txt for full Apache 2.0 license text.
// Sign-off: .planning/phases/07.1-manager-audit-and-basecomponent-fixes/07.1-02-LICENSE-SIGNOFF.md
//
package routines.system;

import java.text.DateFormat;
import java.text.SimpleDateFormat;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * A thread-safe factory for {@link DateFormat} instances, keyed by pattern and locale.
 *
 * <p>Talend-generated code calls this factory to obtain a reusable, thread-local
 * {@link SimpleDateFormat} without re-creating it on every row. The pattern cache
 * avoids the overhead of creating a new {@link SimpleDateFormat} per call.
 *
 * <p>Note: {@link SimpleDateFormat} is NOT thread-safe; instances returned by
 * {@link #getInstance} must NOT be shared across threads. This implementation
 * uses a thread-local cache so each thread gets its own instance.
 */
public class FastDateParser {

    /**
     * Cache key combining pattern and locale.
     */
    private static final class CacheKey {
        final String pattern;
        final Locale locale;

        CacheKey(String pattern, Locale locale) {
            this.pattern = pattern;
            this.locale = locale;
        }

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (!(o instanceof CacheKey)) return false;
            CacheKey other = (CacheKey) o;
            return pattern.equals(other.pattern) && locale.equals(other.locale);
        }

        @Override
        public int hashCode() {
            return 31 * pattern.hashCode() + locale.hashCode();
        }
    }

    /**
     * Thread-local cache: each thread gets its own map of pattern -> DateFormat.
     */
    private static final ThreadLocal<Map<CacheKey, DateFormat>> CACHE =
            ThreadLocal.withInitial(() -> new ConcurrentHashMap<>());

    private FastDateParser() {
        // Utility class; not instantiable
    }

    /**
     * Returns a {@link DateFormat} for the given pattern using the default locale.
     *
     * <p>The returned format is thread-local: it is safe to use on the calling
     * thread without synchronization.
     *
     * @param pattern the {@link SimpleDateFormat} date/time pattern; must not be null
     * @return a DateFormat configured with the given pattern; never null
     */
    public static DateFormat getInstance(String pattern) {
        return getInstance(pattern, Locale.getDefault());
    }

    /**
     * Returns a {@link DateFormat} for the given pattern and locale.
     *
     * <p>The returned format is thread-local: it is safe to use on the calling
     * thread without synchronization.
     *
     * @param pattern the {@link SimpleDateFormat} date/time pattern; must not be null
     * @param locale  the locale to use for formatting; must not be null
     * @return a DateFormat configured with the given pattern and locale; never null
     */
    public static DateFormat getInstance(String pattern, Locale locale) {
        CacheKey key = new CacheKey(pattern, locale);
        Map<CacheKey, DateFormat> cache = CACHE.get();
        DateFormat df = cache.get(key);
        if (df == null) {
            df = new SimpleDateFormat(pattern, locale);
            cache.put(key, df);
        }
        return df;
    }
}
