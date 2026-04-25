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

/**
 * Utility class providing random number generation used by Talend routines.
 *
 * <p>RandomUtils wraps {@link Math#random()} to provide a consistent interface
 * for random number generation across Talend generated code.
 */
public class RandomUtils {

    private RandomUtils() {
        // Utility class; not instantiable
    }

    /**
     * Returns a pseudo-random double value in the range [0.0, 1.0).
     *
     * @return random double in [0.0, 1.0)
     */
    public static double random() {
        return Math.random();
    }
}
