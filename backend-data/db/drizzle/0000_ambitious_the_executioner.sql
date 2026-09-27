CREATE TABLE "constituencies" (
	"id" text PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"state_code" text NOT NULL
);
--> statement-breakpoint
CREATE TABLE "districts" (
	"id" text PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"state_code" text NOT NULL
);
--> statement-breakpoint
CREATE TABLE "states" (
	"code" text PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"district_count" integer DEFAULT 0 NOT NULL
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" text PRIMARY KEY NOT NULL,
	"full_name" text NOT NULL,
	"username" text NOT NULL,
	"designation" text NOT NULL,
	"role" text NOT NULL,
	"state_code" text,
	"district_id" text,
	"constituency_id" text,
	"password_hash" text NOT NULL,
	"scope_id" text NOT NULL,
	"scope_label" text NOT NULL,
	"read_only" boolean DEFAULT false NOT NULL,
	CONSTRAINT "users_username_unique" UNIQUE("username")
);
--> statement-breakpoint
CREATE TABLE "agencies" (
	"agency_id" text PRIMARY KEY NOT NULL,
	"agency_name" text NOT NULL,
	"agency_type" text NOT NULL,
	"state_code" text NOT NULL,
	"district_id" text,
	"is_state_level" boolean DEFAULT false NOT NULL,
	"is_active" boolean DEFAULT true NOT NULL
);
--> statement-breakpoint
CREATE TABLE "assets" (
	"id" integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "assets_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1),
	"work_id" text NOT NULL,
	"stage" text NOT NULL,
	"photo_date" date NOT NULL,
	"uploader" text NOT NULL,
	"gps_status" text NOT NULL,
	"exif_status" text NOT NULL,
	"duplicate_status" text NOT NULL,
	"image_url" text NOT NULL
);
--> statement-breakpoint
CREATE TABLE "payments" (
	"id" integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "payments_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1),
	"work_id" text NOT NULL,
	"tranche" text NOT NULL,
	"payment_date" date NOT NULL,
	"amount" numeric(14, 2) NOT NULL,
	"approver" text NOT NULL,
	"submitted_by" text NOT NULL
);
--> statement-breakpoint
CREATE TABLE "progress_updates" (
	"id" integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "progress_updates_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1),
	"work_id" text NOT NULL,
	"update_date" date NOT NULL,
	"stage" text NOT NULL,
	"progress" numeric(5, 2) NOT NULL,
	"note" text NOT NULL
);
--> statement-breakpoint
CREATE TABLE "projects" (
	"work_id" text PRIMARY KEY NOT NULL,
	"mp_id" text NOT NULL,
	"state_code" text NOT NULL,
	"district_id" text NOT NULL,
	"agency_id" text NOT NULL,
	"constituency_id" text,
	"work_description" text NOT NULL,
	"work_category" text NOT NULL,
	"fiscal_year" text NOT NULL,
	"estimated_cost" numeric(14, 2) NOT NULL,
	"sanctioned_amount" numeric(14, 2) NOT NULL,
	"expenditure_incurred" numeric(14, 2) NOT NULL,
	"physical_progress_pct" numeric(5, 2) NOT NULL,
	"date_of_sanction" date NOT NULL,
	"expected_completion_date" date NOT NULL,
	"actual_completion_date" date,
	"status" text NOT NULL,
	"tender_invited" boolean NOT NULL,
	"uc_filed" boolean NOT NULL,
	"risk_score" integer NOT NULL,
	"risk_level" text NOT NULL,
	"data_completeness" text NOT NULL,
	"workflow_status" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "risk_flags" (
	"id" integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "risk_flags_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1),
	"work_id" text NOT NULL,
	"severity" text NOT NULL,
	"title" text NOT NULL,
	"explanation" text NOT NULL,
	"evidence" text NOT NULL,
	"module" text NOT NULL
);
--> statement-breakpoint
CREATE TABLE "flag_actions" (
	"id" integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "flag_actions_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 2147483647 START WITH 1 CACHE 1),
	"work_id" text NOT NULL,
	"user_id" text NOT NULL,
	"role" text NOT NULL,
	"action" text NOT NULL,
	"timestamp" timestamp with time zone DEFAULT now() NOT NULL,
	"reason" text NOT NULL,
	"from_status" text,
	"to_status" text
);
--> statement-breakpoint
ALTER TABLE "constituencies" ADD CONSTRAINT "constituencies_state_code_states_code_fk" FOREIGN KEY ("state_code") REFERENCES "public"."states"("code") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "districts" ADD CONSTRAINT "districts_state_code_states_code_fk" FOREIGN KEY ("state_code") REFERENCES "public"."states"("code") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "users" ADD CONSTRAINT "users_state_code_states_code_fk" FOREIGN KEY ("state_code") REFERENCES "public"."states"("code") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "users" ADD CONSTRAINT "users_district_id_districts_id_fk" FOREIGN KEY ("district_id") REFERENCES "public"."districts"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "users" ADD CONSTRAINT "users_constituency_id_constituencies_id_fk" FOREIGN KEY ("constituency_id") REFERENCES "public"."constituencies"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agencies" ADD CONSTRAINT "agencies_state_code_states_code_fk" FOREIGN KEY ("state_code") REFERENCES "public"."states"("code") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "agencies" ADD CONSTRAINT "agencies_district_id_districts_id_fk" FOREIGN KEY ("district_id") REFERENCES "public"."districts"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "assets" ADD CONSTRAINT "assets_work_id_projects_work_id_fk" FOREIGN KEY ("work_id") REFERENCES "public"."projects"("work_id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "payments" ADD CONSTRAINT "payments_work_id_projects_work_id_fk" FOREIGN KEY ("work_id") REFERENCES "public"."projects"("work_id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "progress_updates" ADD CONSTRAINT "progress_updates_work_id_projects_work_id_fk" FOREIGN KEY ("work_id") REFERENCES "public"."projects"("work_id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "projects" ADD CONSTRAINT "projects_mp_id_users_id_fk" FOREIGN KEY ("mp_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "projects" ADD CONSTRAINT "projects_state_code_states_code_fk" FOREIGN KEY ("state_code") REFERENCES "public"."states"("code") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "projects" ADD CONSTRAINT "projects_district_id_districts_id_fk" FOREIGN KEY ("district_id") REFERENCES "public"."districts"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "projects" ADD CONSTRAINT "projects_agency_id_agencies_agency_id_fk" FOREIGN KEY ("agency_id") REFERENCES "public"."agencies"("agency_id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "projects" ADD CONSTRAINT "projects_constituency_id_constituencies_id_fk" FOREIGN KEY ("constituency_id") REFERENCES "public"."constituencies"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "risk_flags" ADD CONSTRAINT "risk_flags_work_id_projects_work_id_fk" FOREIGN KEY ("work_id") REFERENCES "public"."projects"("work_id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "flag_actions" ADD CONSTRAINT "flag_actions_work_id_projects_work_id_fk" FOREIGN KEY ("work_id") REFERENCES "public"."projects"("work_id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "flag_actions" ADD CONSTRAINT "flag_actions_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;