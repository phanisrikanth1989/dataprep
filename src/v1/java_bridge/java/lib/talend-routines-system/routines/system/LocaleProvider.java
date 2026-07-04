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

import java.util.Locale;

/**
 * Utility class for resolving a language or country code string to a {@link Locale}.
 *
 * <p>Used by Talend-generated date formatting code where the user supplies a
 * language/country code string (e.g. "en", "fr", "en_US").
 */
public class LocaleProvider {

    private LocaleProvider() {
        // Utility class; not instantiable
    }

    /**
     * Returns a {@link Locale} for the given language or country code string.
     *
     * <p>Accepts:
     * <ul>
     *   <li>simple language tag: "en", "fr", "de"</li>
     *   <li>language_COUNTRY tag: "en_US", "fr_FR", "zh_CN"</li>
     *   <li>IETF BCP 47 tag (via {@link Locale#forLanguageTag}): "en-US"</li>
     * </ul>
     *
     * @param languageOrCountryCode the locale string; if null or blank, returns {@link Locale#getDefault()}
     * @return resolved {@link Locale}, never null
     */
    public static Locale getLocale(String languageOrCountryCode) {
        if (languageOrCountryCode == null || languageOrCountryCode.trim().isEmpty()) {
            return Locale.getDefault();
        }
        String code = languageOrCountryCode.trim();
        // Handle underscore-delimited language_COUNTRY format (e.g. "en_US")
        if (code.contains("_")) {
            String[] parts = code.split("_", 3);
            if (parts.length == 2) {
                return new Locale(parts[0], parts[1]);
            } else if (parts.length == 3) {
                return new Locale(parts[0], parts[1], parts[2]);
            }
        }
        // Handle hyphen-delimited IETF BCP 47 format (e.g. "en-US")
        if (code.contains("-")) {
            return Locale.forLanguageTag(code);
        }
        // Simple language code (e.g. "en", "fr")
        return new Locale(code);
    }
}
