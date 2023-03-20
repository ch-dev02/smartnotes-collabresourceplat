from app import app, db, models
from flask import render_template, request, flash, redirect, url_for
from flask_login import current_user, login_required
from ..forms import *
import logging
import html
import json
import time
import math

logger = logging.getLogger(__name__)

"""
Create Review
POST request only
Requires login
If form validates
  - Get resource
  - If resource does not exist
      - Flash & log error, redirect to index
  - Get folder
  - If folder does not exist
      - Flash & log error, redirect to index
  - Get group
  - If group does not exist
      - Flash & log error, redirect to index
  - If user is resource creator
      - Flash & log error, redirect to resource
  - If user is not a member of the group
      - Flash & log error, redirect to resource
  - If user has already reviewed this resource
      - Flash & log error, redirect to resource
  - Validate rating between 1 and 5 (inclusive)
  - If rating is not valid
      - Flash & log error, redirect to resource
  - Validate Comment length < 256 and html escape
  - If comment is not valid
      - Flash & log error, redirect to resource
  - Create review, Flash success, redirect to resource
If form does not validate
  - Flash & log error, redirect to resource
"""
@app.route("/review", methods=["POST"])
@login_required
def review():
    form = ReviewForm()
    if form.validate_on_submit():
        resource = models.Resource.query.filter_by(id=form.resource_id.data).first()
        if not resource:
            flash("Resource not found!", "danger")
            logger.warning("User %s tried to review a resource that does not exist!", current_user.email)
            return redirect(url_for("index"))
        folder = models.Folder.query.filter_by(id=resource.folder).first()
        if not folder:
            flash("Folder not found!", "danger")
            logger.warning("User %s tried to review a resource in a folder that does not exist!", current_user.email)
            return redirect(url_for("index"))
        group = models.Group.query.filter_by(id=folder.group).first()
        if not group:
            flash("Group not found!", "danger")
            logger.warning("User %s tried to review a resource in a group that does not exist!", current_user.email)
            return redirect(url_for("index"))
        if current_user.id == resource.creator:
            flash("You cannot review your own resource!", "danger")
            logger.info("User %s tried to review their own resource!", current_user.email)
            return redirect(url_for("resource", id=resource.id))
        if not models.Member.query.filter_by(group=group.id, user=current_user.id).first() and not current_user.id == group.owner:
            flash("You cannot review a resource in a group you are a member of!", "danger")
            logger.warning("User %s tried to review a resource in a group they are not a member of!", current_user.email)
            return redirect(url_for("index"))
        if models.Review.query.filter_by(creator=current_user.id, resource=resource.id).first():
            flash("You have already reviewed this resource!", "danger")
            logger.info("User %s tried to review a resource they have already reviewed!", current_user.email)
            return redirect(url_for("resource", id=resource.id))
        comment = html.escape(form.review.data)
        if len(comment) > 256:
            flash("Comment too long!", "danger")
            logger.info("User %s tried to review a resource with a comment that was too long!", current_user.email)
            return redirect(url_for("resource", id=resource.id))
        rating = int(form.rating.data)
        if rating < 0 or rating > 5:
            flash("Invalid rating!", "danger")
            logger.info("User %s tried to review a resource with an invalid rating!", current_user.email)
            return redirect(url_for("resource", id=resource.id))
        review = models.Review(creator=current_user.id, resource=resource.id, comment=comment, rating=rating)
        db.session.add(review)
        db.session.commit()
        flash("Review created!", "success")
        logger.info("User %s created a review for resource %s!", current_user.email, resource.id)
        return redirect(url_for("resource", id=resource.id))
    else:
        flash("Invalid form!", "danger")
        return redirect(url_for("index"))

"""
Delete Review
POST request only
Requires login
If form validates
    - Get review
    - If review does not exist
        - Flash & log error, redirect to index 
    - Get resource
    - If resource does not exist
        - Flash & log error, redirect to index
    - Get folder
    - If folder does not exist
        - Flash & log error, redirect to index
    - If user is not the review creator or the group owner
        - Flash & log error, redirect to resource
    - Delete review, Flash success, redirect to resource
If form does not validate
    - Flash & log error, redirect to index
"""
@app.route("/review/delete", methods=["POST"])
@login_required
def delete_review():
    form = DelReviewForm()
    if form.validate_on_submit():
        review = models.Review.query.filter_by(id=form.review_id.data).first()
        if not review:
            flash("Review not found!", "danger")
            logger.warning("User %s tried to delete a review that does not exist!", current_user.email)
            return redirect(url_for("index"))
        resource = models.Resource.query.filter_by(id=review.resource).first()
        if not resource:
            flash("Resource not found!", "danger")
            logger.warning("User %s tried to delete a review for a resource that does not exist!", current_user.email)
            return redirect(url_for("index"))
        folder = models.Folder.query.filter_by(id=resource.folder).first()
        if not folder:
            flash("Folder not found!", "danger")
            logger.warning("User %s tried to delete a review for a resource in a folder that does not exist!", current_user.email)
            return redirect(url_for("index"))
        group = models.Group.query.filter_by(id=folder.group).first()
        if not group:
            flash("Group not found!", "danger")
            logger.warning("User %s tried to delete a review for a resource in a group that does not exist!", current_user.email)
            return redirect(url_for("index"))
        if not current_user.id == review.creator and not current_user.id == group.owner:
            flash("You cannot delete this review!", "danger")
            logger.warning("User %s tried to delete a review they did not create!", current_user.email)
            return redirect(url_for("index"))
        db.session.delete(review)
        db.session.commit()
        flash("Review deleted!", "success")
        logger.info("User %s deleted a review for resource %s!", current_user.email, resource.id)
        return redirect(url_for("resource", id=resource.id))
    else:
        flash("Invalid form!", "danger")
        logger.error("User %s tried to delete a review with an invalid form!", current_user.email)
        return redirect(url_for("index"))

"""
Report Review
User must be logged in
Post Request Only
If Form doesn't validate, redirect to index, flash and log error
Else
 - Check if review exists
 - Check resource exists
 - Check folder exists
 - Check parent group exists
 - Check users is creator or group owner
    - They can delete the review on request already so no need to report
 - Check if review was created by group owner
    - If so do nothing, not allowed to report the owners reviews
 - Check if review was already reported by user
    - If so do nothing, already reported
 - Check if creating report would exceed max reports
    - If so delete review
 - Otherwise Create report
"""
@app.route("/review/report", methods=["POST"])
@login_required
def report_review():
    form = DelReviewForm()
    if form.validate_on_submit():
        review = models.Review.query.filter_by(id=form.review_id.data).first()
        if not review:
            flash("Review not found!", "danger")
            logger.warning("User %s tried to report a review that does not exist!", current_user.email)
            return redirect(url_for("index"))
        resource = models.Resource.query.filter_by(id=review.resource).first()
        if not resource:
            flash("Resource not found!", "danger")
            logger.warning("User %s tried to report a review for a resource that does not exist!", current_user.email)
            return redirect(url_for("index"))
        folder = models.Folder.query.filter_by(id=resource.folder).first()
        if not folder:
            flash("Folder not found!", "danger")
            logger.warning("User %s tried to report a review for a resource in a folder that does not exist!", current_user.email)
            return redirect(url_for("index"))
        group = models.Group.query.filter_by(id=folder.group).first()
        if not group:
            flash("Group not found!", "danger")
            logger.warning("User %s tried to report a review for a resource in a group that does not exist!", current_user.email)
            return redirect(url_for("index"))
        if current_user.id == review.creator or current_user.id == group.owner:
            flash("You cannot report reviews you have the ability to delete", "danger")
            logger.warning("User %s tried to report a review they can delete!", current_user.email)
            return redirect("/resource/"+str(resource.id))
        if review.creator == group.owner:
            flash("You cannot report the group owners reviews", "danger")
            logger.warning("User %s tried to report a review created by the group owner!", current_user.email)
            return redirect("/resource/"+str(resource.id))
        if models.Report.query.filter_by(item=review.id, type="review", user=current_user.id).first():
            flash("You have already reported this review", "danger")
            logger.warning("User %s tried to report a review they have already reported!", current_user.email)
            return redirect("/resource/"+str(resource.id))
        reports = models.Report.query.filter_by(item=form.review_id.data, type="review").all()
        num_members = len(models.Member.query.filter_by(group=group.id).all())
        req_rep = max(5, math.ceil(num_members * 0.05))
        if req_rep >= num_members:
            req_rep = num_members - 1 # -1 as creator cannot report own review
        if len(reports)+1 >= req_rep:
            db.session.delete(review)
            for report in reports:
                db.session.delete(report)
            db.session.commit()
            logger.info("Review %d has been deleted for exceeding max reports!", resource.id)
        else:
            report = models.Report(item=form.review_id.data, type="review", user=current_user.id)
            db.session.add(report)
            logger.info("User %s reported a review for resource %s!", current_user.email, resource.id)
        flash("Review reported!", "success")
        db.session.commit()
        return redirect(url_for("resource", id=resource.id))
    else:
        flash("Invalid form!", "danger")
        logger.error("User %s tried to report a review with an invalid form!", current_user.email)
        return redirect(url_for("index"))