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

import java.sql.Timestamp;
import java.util.TimeZone;

/**
 * A {@link Timestamp} that carries an associated {@link TimeZone}.
 *
 * <p>Talend uses this class to represent timestamps where the timezone is known
 * and must be preserved during formatting/parsing operations.
 */
public class TalendTimestampWithTZ extends Timestamp {

    private static final long serialVersionUID = 1L;

    private final TimeZone timeZone;

    /**
     * Constructs a TalendTimestampWithTZ from an existing {@link Timestamp} and a {@link TimeZone}.
     *
     * @param timestamp the timestamp value; must not be null
     * @param timeZone  the associated timezone; must not be null
     */
    public TalendTimestampWithTZ(Timestamp timestamp, TimeZone timeZone) {
        super(timestamp.getTime());
        setNanos(timestamp.getNanos());
        this.timeZone = timeZone;
    }

    /**
     * Returns the timezone associated with this timestamp.
     *
     * @return the {@link TimeZone}; never null
     */
    public TimeZone getTimeZone() {
        return timeZone;
    }

    @Override
    public String toString() {
        return super.toString() + " [" + timeZone.getID() + "]";
    }
}
