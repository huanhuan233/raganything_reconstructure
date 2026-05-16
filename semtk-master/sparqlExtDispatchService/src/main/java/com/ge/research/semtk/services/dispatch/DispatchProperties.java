/**
 ** Copyright 2016 General Electric Company
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

package com.ge.research.semtk.services.dispatch;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

import com.ge.research.semtk.properties.Properties;

@Configuration
@ConfigurationProperties(prefix="dispatch", ignoreUnknownFields = true)
public class DispatchProperties extends Properties {	
	private String dispatcherClassName;
	
	public DispatchProperties() {
		super();
		this.setPrefix("dispatch");
	}
	
	public String getDispatcherClassName() {
		return dispatcherClassName;
	}
	public void setDispatcherClassName(String dispatcherClassName) {
		this.dispatcherClassName = dispatcherClassName;
	}

	public void validate() throws Exception {
		super.validate();
		checkNotEmpty("dispatcherClassName", dispatcherClassName);
	}
	
}
