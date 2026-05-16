/**
 ** Copyright 2019 General Electric Company
 **
 **
 ** Licensed under the Apache License, Version 2.0 (the "License");
 ** you may not use this file except in compliance with the License.
 ** You may obtain a copy of the License at
 ** 
 **     http://www.apache.org/licenses/LICENSE-2.0
 ** 
 ** Unless required by applicable law or agreed to in writing, software
 ** distributed under the License is distributed on an "AS IS" BASIS,
 ** WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 ** See the License for the specific language governing permissions and
 ** limitations under the License.
 */


package com.ge.research.semtk.springutilib.requests;

import javax.validation.constraints.Digits;
import javax.validation.constraints.NotNull;
import javax.validation.constraints.Size;

public abstract class DatabaseRequest {
	
	@NotNull
	@Size(min=5, message="host must be at least 5 characters in length")
    public String host;
	
	@NotNull
	@Digits(integer=5, fraction=0)
    public String port;
	
	@NotNull
	@Size(min=2, message="database must be at least 2 characters in length")
    public String database;
}
